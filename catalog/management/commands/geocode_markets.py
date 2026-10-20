"""Refine market coordinates from OpenStreetMap (Nominatim, falling back to Photon).

    python manage.py geocode_markets            # unverified markets only
    python manage.py geocode_markets --dry-run  # show changes without saving
    python manage.py geocode_markets --market yiwu

A result is only accepted if it lies within --max-km of the current pin, so a
bad match on the other side of China is ignored. Markets you have ticked as
"location verified" are never touched.
"""

import time
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError

from catalog import osm
from catalog.models import Market
from travel.models import distance_km

MAX_FAILURES_IN_A_ROW = 5


class Command(BaseCommand):
    help = "Refine unverified market coordinates from OpenStreetMap."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--max-km", type=float, default=15)
        parser.add_argument("--ids", help="Comma-separated database ids (used by the admin actions).")
        parser.add_argument("--market", help="Only markets whose slug contains this text.")

    def handle(self, *args, **opts):
        osm.contact()
        markets = Market.objects.filter(location_verified=False)
        if opts["market"]:
            markets = markets.filter(slug__contains=opts["market"])
        if opts["ids"]:
            markets = markets.filter(pk__in=[int(i) for i in opts["ids"].split(",") if i.strip()])

        moved = failures = 0
        for m in markets:
            queries = [q for q in (m.name_zh, f"{m.name}, {m.city}", m.address_zh, f"{m.address}, {m.city}") if q]
            near = (float(m.latitude), float(m.longitude)) if m.has_coordinates else None
            hit, error = None, None
            for q in queries:
                try:
                    hit = osm.geocode(q, near=near)
                except osm.ProviderError as exc:
                    raise CommandError(self._blocked_help(exc))
                except Exception as exc:
                    error = exc
                time.sleep(1.1)  # Nominatim usage policy: at most 1 request per second
                if hit:
                    break
            self._print_notes()

            if error and not hit:
                failures += 1
                self.stdout.write(self.style.ERROR(f"✗ {m} — {error}"))
                if failures >= MAX_FAILURES_IN_A_ROW:
                    raise CommandError(f"Stopped after {failures} failures in a row (last: {error}). "
                                       "Check your internet connection and try again later.")
                continue
            failures = 0
            if not hit:
                self.stdout.write(f"· {m} — no match, keeping current pin")
                continue
            lat, lon, label = hit
            if near and distance_km(near[0], near[1], lat, lon) > opts["max_km"]:
                self.stdout.write(self.style.WARNING(f"? {m} — match too far away ({label[:60]}), skipped"))
                continue
            self.stdout.write(self.style.SUCCESS(f"✓ {m} → {lat:.5f}, {lon:.5f}  {label[:70]}"))
            moved += 1
            if not opts["dry_run"]:
                m.latitude, m.longitude = Decimal(f"{lat:.6f}"), Decimal(f"{lon:.6f}")
                m.save(update_fields=["latitude", "longitude"])

        self.stdout.write(f"\nDone: {moved} market pin(s) {'would be ' if opts['dry_run'] else ''}updated.")

    def _print_notes(self):
        while osm.notes:
            self.stdout.write(self.style.WARNING(f"! {osm.notes.pop(0)}"))

    def _blocked_help(self, exc):
        return (f"{exc}.\nYour contact e-mail is set, so these services are likely blocking your network "
                "(VPNs and shared office IPs are often blocked). Try again from another connection, "
                "or set the coordinates by hand in the admin.")
