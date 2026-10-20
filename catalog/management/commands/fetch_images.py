"""Download real, freely-licensed photos from Wikimedia Commons.

For every market / product / category without an uploaded photo, this searches
Commons with the record's `image_query`, picks the largest landscape photo,
and stores it at up to 3840 px wide (4K). Author and licence are saved in
`image_credit` so you can show attribution.

    python manage.py fetch_images                 # fill in missing photos
    python manage.py fetch_images --force         # replace existing photos too
    python manage.py fetch_images --only markets  # markets | products | categories
"""

import json
import re
import time
import urllib.parse
import urllib.request
from html import unescape

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from catalog import osm
from catalog.models import Category, Market, Product

API = "https://commons.wikimedia.org/w/api.php"


def _get(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": osm.user_agent()})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _clean(html):
    return unescape(re.sub(r"<[^>]+>", "", html or "")).strip()


def search_commons(query, width, limit=12):
    params = {
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": f"{query} filetype:bitmap", "gsrnamespace": 6, "gsrlimit": limit,
        "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata", "iiurlwidth": width,
    }
    data = json.loads(_get(API + "?" + urllib.parse.urlencode(params)))
    results = []
    for page in data.get("query", {}).get("pages", {}).values():
        info = (page.get("imageinfo") or [{}])[0]
        if info.get("mime") not in {"image/jpeg", "image/png", "image/webp"}:
            continue
        meta = info.get("extmetadata", {})
        results.append({
            "title": page.get("title", ""),
            "width": info.get("width", 0),
            "height": info.get("height", 0),
            "url": info.get("thumburl") or info.get("url"),
            "page": info.get("descriptionurl", ""),
            "artist": _clean(meta.get("Artist", {}).get("value")),
            "license": _clean(meta.get("LicenseShortName", {}).get("value")),
            "rank": page.get("index", 99),
        })
    return results


def pick_best(results, min_width=1600):
    """Prefer landscape, high-resolution photos; keep search relevance as tiebreak."""
    def score(r):
        landscape = r["width"] >= r["height"] * 1.15
        big = r["width"] >= min_width
        return (landscape and big, big, landscape, -r["rank"], r["width"])

    return max(results, key=score) if results else None


class Command(BaseCommand):
    help = "Fetch real high-resolution photos (up to 4K) from Wikimedia Commons."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Replace photos that already exist.")
        parser.add_argument("--only", choices=["markets", "products", "categories"])
        parser.add_argument("--ids", help="Comma-separated database ids (used by the admin actions).")
        parser.add_argument("--width", type=int, default=3840, help="Target width in px (default 3840 = 4K).")

    def handle(self, *args, **opts):
        osm.contact()  # fail early with instructions if no contact e-mail is set
        groups = {"markets": Market, "products": Product, "categories": Category}
        if opts["only"]:
            groups = {opts["only"]: groups[opts["only"]]}

        ok = failed = 0
        for label, model in groups.items():
            self.stdout.write(self.style.MIGRATE_HEADING(f"\n{label.title()}"))
            objects = model.objects.all()
            if opts["ids"]:
                objects = objects.filter(pk__in=[int(i) for i in opts["ids"].split(",") if i.strip()])
            for obj in objects:
                if obj.image and not opts["force"]:
                    self.stdout.write(f"  · {obj} — already has a photo")
                    continue
                query = obj.image_query or obj.name
                try:
                    best = pick_best(search_commons(query, opts["width"]))
                    if not best:
                        self.stdout.write(self.style.WARNING(f"  ✗ {obj} — no photo found for “{query}”"))
                        failed += 1
                        continue
                    content = _get(best["url"], timeout=120)
                    ext = ".png" if best["url"].lower().endswith(".png") else ".jpg"
                    if obj.image:
                        obj.image.delete(save=False)
                    obj.image.save(f"{obj.slug}{ext}", ContentFile(content), save=False)
                    credit = " · ".join(filter(None, [best["artist"], best["license"], "Wikimedia Commons"]))
                    obj.image_credit = credit[:300]
                    obj.image_source = best["page"][:600]
                    obj.save()
                    ok += 1
                    self.stdout.write(self.style.SUCCESS(
                        f"  ✓ {obj} — {best['title']} ({min(best['width'], opts['width'])}px)"
                    ))
                    time.sleep(0.5)  # be polite to Wikimedia
                except Exception as exc:  # network errors etc. shouldn't stop the batch
                    failed += 1
                    self.stdout.write(self.style.ERROR(f"  ✗ {obj} — {exc}"))

        self.stdout.write(f"\nDone: {ok} photos saved, {failed} skipped.")
        if failed:
            self.stdout.write("Tip: edit `image_query` in the admin for skipped items, or upload your own photo.")
