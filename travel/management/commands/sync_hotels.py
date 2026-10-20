"""Find real hotels near every market using OpenStreetMap (free, no API key).

    python manage.py sync_hotels                 # all markets with coordinates
    python manage.py sync_hotels --market yiwu   # markets whose slug contains "yiwu"
    python manage.py sync_hotels --radius 3000   # search radius in metres

Tries the Overpass servers in OVERPASS_URLS, then falls back to Photon. Run it
on a schedule (e.g. weekly cron) so new hotels appear on the site
automatically. Hotels your team added by hand are never overwritten.
"""

import time
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from catalog import osm
from catalog.models import Market
from travel.models import City, Hotel, MarketHotel, distance_km

MAX_FAILURES_IN_A_ROW = 4


def parse(el):
    tags = el.get("tags", {})
    lat = el.get("lat") or el.get("center", {}).get("lat")
    lon = el.get("lon") or el.get("center", {}).get("lon")
    name_en = tags.get("name:en") or ""
    name_zh = tags.get("name:zh") or ""
    name = tags.get("name") or ""
    if not name_en and name.isascii():
        name_en = name
    if not name_zh and not name.isascii():
        name_zh = name
    if not (lat and lon and el.get("id") and (name_en or name_zh)):
        return None
    stars = tags.get("stars", "")[:1]
    address = tags.get("addr:full") or " ".join(
        filter(None, [tags.get("addr:housenumber"), tags.get("addr:street"), tags.get("addr:district")])
    )
    return {
        "osm_id": f"{el.get('type', 'node')}/{el['id']}",
        "name": name_en or name_zh,
        "name_zh": name_zh,
        "latitude": Decimal(str(round(lat, 6))),
        "longitude": Decimal(str(round(lon, 6))),
        "stars": int(stars) if stars.isdigit() else None,
        "brand": tags.get("brand:en") or tags.get("brand") or "",
        "website": (tags.get("website") or tags.get("contact:website") or "")[:400],
        "phone": (tags.get("phone") or tags.get("contact:phone") or "")[:60],
        "address": address[:255],
    }


def rank(h):
    """Prefer hotels international visitors can find: English name, brand, stars."""
    return (h["name"].isascii(), bool(h["brand"]), h["stars"] or 0, -h["distance"])


class Command(BaseCommand):
    help = "Pull hotels near each market from OpenStreetMap and link them to the market."

    def add_arguments(self, parser):
        parser.add_argument("--market", help="Only markets whose slug contains this text.")
        parser.add_argument("--ids", help="Comma-separated database ids (used by the admin actions).")
        parser.add_argument("--radius", type=int, default=settings.HOTEL_SEARCH_RADIUS_M)
        parser.add_argument("--limit", type=int, default=settings.HOTELS_PER_MARKET)

    def handle(self, *args, **opts):
        osm.contact()
        markets = Market.objects.exclude(latitude=None).exclude(longitude=None)
        if opts["market"]:
            markets = markets.filter(slug__contains=opts["market"])
        if opts["ids"]:
            markets = markets.filter(pk__in=[int(i) for i in opts["ids"].split(",") if i.strip()])

        total = failures = 0
        for market in markets:
            city, _ = City.objects.get_or_create(name=market.city, defaults={"province": market.province})
            try:
                elements = osm.hotels_near(market.latitude, market.longitude, opts["radius"])
            except osm.ProviderError as exc:
                self._print_notes()
                failures += 1
                self.stdout.write(self.style.ERROR(f"✗ {market} — {exc}"))
                if exc.refused or failures >= MAX_FAILURES_IN_A_ROW:
                    reason = ("Stopped: every map server refused our requests." if exc.refused
                              else f"Stopped after {failures} markets failed in a row.")
                    raise CommandError(
                        f"{reason}\n"
                        "Your contact e-mail is set, so the map servers are probably busy or blocking your network "
                        "(VPNs and shared office IPs are often blocked). Wait a few minutes or try another "
                        "connection, then re-run; markets already done are kept."
                    )
                time.sleep(5)
                continue
            self._print_notes()
            failures = 0

            found = []
            for el in elements:
                h = parse(el)
                if h:
                    h["distance"] = distance_km(market.latitude, market.longitude, h["latitude"], h["longitude"])
                    found.append(h)
            found.sort(key=rank, reverse=True)

            linked = 0
            for h in found[: opts["limit"]]:
                distance = h.pop("distance")
                hotel = Hotel.objects.filter(osm_id=h["osm_id"]).first()
                if hotel is None:
                    hotel = Hotel.objects.create(city=city, source=Hotel.Source.OSM, **h)
                elif hotel.source == Hotel.Source.OSM:
                    for k, v in h.items():
                        setattr(hotel, k, v)
                    hotel.save()
                MarketHotel.objects.update_or_create(
                    market=market, hotel=hotel, defaults={"distance_km": Decimal(str(round(distance, 2)))}
                )
                linked += 1
            total += linked
            style = self.style.SUCCESS if linked else self.style.WARNING
            self.stdout.write(style(f"{'✓' if linked else '·'} {market} — {linked} hotels"))
            time.sleep(2)  # fair use

        # Link hand-added hotels to nearby markets too.
        for hotel in Hotel.objects.filter(source=Hotel.Source.MANUAL):
            for market in Market.objects.filter(city=hotel.city.name).exclude(latitude=None):
                d = distance_km(market.latitude, market.longitude, hotel.latitude, hotel.longitude)
                if d * 1000 <= opts["radius"] * 2:
                    MarketHotel.objects.update_or_create(
                        market=market, hotel=hotel, defaults={"distance_km": Decimal(str(round(d, 2)))}
                    )
        self.stdout.write(f"\nDone: {total} market–hotel links.")

    def _print_notes(self):
        while osm.notes:
            self.stdout.write(self.style.WARNING(f"! {osm.notes.pop(0)}"))
