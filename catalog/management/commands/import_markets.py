"""Bulk-add or update markets from a CSV file.

    python manage.py import_markets markets.csv

Columns (header row required; only name, city and province are mandatory):
    name, name_zh, city, province, categories, specialty, summary, description,
    address, address_zh, latitude, longitude, opening_hours, booths, image_query

`categories` is a space-separated list of category slugs, e.g. "apparel bags".
Existing markets are matched by name and updated.
"""

import csv
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from catalog.models import Category, Market

TEXT = ["name_zh", "city", "province", "specialty", "summary", "description", "address", "address_zh",
        "opening_hours", "image_query"]


class Command(BaseCommand):
    help = "Import markets from a CSV file."

    def add_arguments(self, parser):
        parser.add_argument("csv_path")

    @transaction.atomic
    def handle(self, csv_path, **opts):
        cats = {c.slug: c for c in Category.objects.all()}
        created = updated = 0
        try:
            fh = open(csv_path, newline="", encoding="utf-8-sig")
        except OSError as exc:
            raise CommandError(exc)
        with fh:
            for i, row in enumerate(csv.DictReader(fh), start=2):
                name = (row.get("name") or "").strip()
                if not name or not row.get("city") or not row.get("province"):
                    self.stdout.write(self.style.WARNING(f"Row {i}: name, city and province are required — skipped"))
                    continue
                data = {k: row[k].strip() for k in TEXT if row.get(k)}
                data.setdefault("specialty", "General wholesale")
                data.setdefault("summary", f"Wholesale market in {data['city']}.")
                data.setdefault("description", data["summary"])
                try:
                    for k in ("latitude", "longitude"):
                        if row.get(k):
                            data[k] = Decimal(row[k].strip())
                except InvalidOperation:
                    self.stdout.write(self.style.WARNING(f"Row {i}: bad coordinates — skipped"))
                    continue
                if (row.get("booths") or "").strip().isdigit():
                    data["booths"] = int(row["booths"])
                market, is_new = Market.objects.update_or_create(name=name, defaults=data)
                wanted = [cats[s] for s in (row.get("categories") or "").split() if s in cats]
                if wanted:
                    market.categories.set(wanted)
                created += is_new
                updated += not is_new
        self.stdout.write(self.style.SUCCESS(f"{created} markets added, {updated} updated."))
