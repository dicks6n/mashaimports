"""Shared HTTP helpers for OpenStreetMap-based services and Wikimedia.

These services are free but require every request to identify the app and
give a real contact e-mail (their usage policies). Requests with a missing or
placeholder contact are refused: Nominatim answers 403, Overpass 406.

Order of providers:
    geocoding: Nominatim  -> Photon (komoot)
    hotels:    Overpass mirrors (OVERPASS_URLS) -> Photon (komoot)
A provider that refuses us (403/406/429) is skipped for the rest of the run.
"""

import json
import math
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from django.core.management.base import CommandError

NOMINATIM = "https://nominatim.openstreetmap.org/search"
PHOTON = "https://photon.komoot.io/api/"
REFUSED = {403, 406, 429}

_skipped = set()  # providers that refused us during this run
notes = []  # human-readable notes about fallbacks, printed by the commands


class ProviderError(Exception):
    def __init__(self, message, refused=False):
        super().__init__(message)
        self.refused = refused  # True when every provider actively refused us


def contact():
    email = (settings.OSM_CONTACT_EMAIL or "").strip()
    looks_valid = (
        email.count("@") == 1 and " " not in email and "." in email.split("@")[-1]
        and "example." not in email and "yourdomain" not in email
    )
    if not looks_valid:
        env_file = settings.BASE_DIR / ".env"
        found = "found" if env_file.exists() else "NOT FOUND — create it"
        raise CommandError(
            "OpenStreetMap and Wikimedia refuse requests without a real contact e-mail.\n\n"
            f"  .env file:                 {env_file}  ({found})\n"
            f"  OSM_CONTACT_EMAIL is now:  {email or '(empty)'}\n\n"
            "Put this line in that .env file, on its own line, with only your address after the = sign:\n\n"
            "    OSM_CONTACT_EMAIL=name@yourmail.com\n"
        )
    return email


def user_agent():
    site = f"; +{settings.SITE_URL}" if settings.SITE_URL else ""
    return f"{settings.SITE_NAME.replace(' ', '')}/1.0 (contact: {contact()}{site})"


def get_json(url, data=None, timeout=60):
    headers = {
        "User-Agent": user_agent(),
        "Accept": "application/json",
        "Accept-Language": "en,zh;q=0.8",
    }
    if settings.SITE_URL:
        headers["Referer"] = settings.SITE_URL
    if data is not None:
        data = urllib.parse.urlencode(data).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _host(url):
    return urllib.parse.urlparse(url).netloc


def _refused(name, exc):
    _skipped.add(name)
    notes.append(f"{name} refused our requests (HTTP {exc.code}); using the next provider instead.")


# --- Geocoding --------------------------------------------------------------

def geocode(query, near=None):
    """Return (lat, lon, label) or None. `near` = (lat, lon) biases Photon results."""
    if "nominatim" not in _skipped:
        params = {"q": query, "format": "json", "limit": 1, "countrycodes": "cn", "email": contact()}
        try:
            data = get_json(NOMINATIM + "?" + urllib.parse.urlencode(params), timeout=30)
            if data:
                return float(data[0]["lat"]), float(data[0]["lon"]), data[0].get("display_name", "")
            return None
        except urllib.error.HTTPError as exc:
            if exc.code not in REFUSED:
                raise
            _refused("nominatim", exc)

    if "photon" in _skipped:
        raise ProviderError("every geocoding provider refused our requests", refused=True)
    params = {"q": query, "limit": 1, "lang": "en"}
    if near:
        params.update({"lat": near[0], "lon": near[1]})
    try:
        data = get_json(PHOTON + "?" + urllib.parse.urlencode(params), timeout=30)
    except urllib.error.HTTPError as exc:
        if exc.code in REFUSED:
            _refused("photon", exc)
            raise ProviderError("every geocoding provider refused our requests", refused=True) from exc
        raise
    for feat in data.get("features", []):
        props = feat.get("properties", {})
        if props.get("countrycode", "CN").upper() != "CN":
            continue
        lon, lat = feat["geometry"]["coordinates"][:2]
        label = ", ".join(filter(None, [props.get("name"), props.get("street"), props.get("city")]))
        return float(lat), float(lon), label
    return None


# --- Hotels -----------------------------------------------------------------

def hotels_near(lat, lon, radius):
    """Return OSM elements tagged tourism=hotel within `radius` metres."""
    query = f"""
    [out:json][timeout:90];
    ( node["tourism"="hotel"](around:{radius},{lat},{lon});
      way["tourism"="hotel"](around:{radius},{lat},{lon}); );
    out center tags 80;
    """
    last_error = None
    for url in settings.OVERPASS_URLS:
        name = _host(url)
        if name in _skipped:
            continue
        try:
            return get_json(url, data={"data": query}, timeout=120).get("elements", [])
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code in REFUSED:
                _refused(name, exc)
            # 5xx (busy) or refusal: try the next mirror
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc  # timeout / network: try the next mirror for this market

    if "photon" not in _skipped:
        try:
            return _photon_hotels(lat, lon, radius)
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code in REFUSED:
                _refused("photon", exc)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
    providers = {_host(u) for u in settings.OVERPASS_URLS} | {"photon"}
    if providers <= _skipped:
        raise ProviderError("every hotel provider refused our requests", refused=True)
    raise ProviderError(f"no hotel provider answered ({last_error})")


def _photon_hotels(lat, lon, radius):
    """Photon fallback, converted to the same shape as Overpass elements."""
    seen, out = set(), []
    for word in ("hotel", "酒店", "宾馆"):
        params = [("q", word), ("lat", lat), ("lon", lon), ("limit", 40), ("osm_tag", "tourism:hotel")]
        data = get_json(PHOTON + "?" + urllib.parse.urlencode(params), timeout=60)
        for feat in data.get("features", []):
            p = feat.get("properties", {})
            h_lon, h_lat = feat["geometry"]["coordinates"][:2]
            key = (p.get("osm_type"), p.get("osm_id"))
            if key in seen or _distance_m(lat, lon, h_lat, h_lon) > radius:
                continue
            seen.add(key)
            address = " ".join(filter(None, [p.get("housenumber"), p.get("street"), p.get("district")]))
            out.append({
                "type": {"N": "node", "W": "way", "R": "relation"}.get(p.get("osm_type"), "node"),
                "id": p.get("osm_id"),
                "lat": h_lat,
                "lon": h_lon,
                "tags": {"name": p.get("name", ""), "tourism": "hotel", "addr:full": address},
            })
    return out


def _distance_m(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(math.radians, map(float, (lat1, lon1, lat2, lon2)))
    a = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371000 * 2 * math.asin(math.sqrt(a))
