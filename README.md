# Masha Imports — Shipping & Sourcing from China

A Django site where customers pay a **flat $50 sourcing fee** to have an agent find any product in China's
wholesale markets and ship it to them, **or** buy a **Location Pass** to unlock market addresses and maps so they can go themselves.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # then set OSM_CONTACT_EMAIL to your real e-mail
python manage.py migrate
python manage.py seed_data          # 122 markets, 58 cities, 17 categories, 54 products, 10 services, 3 passes
python manage.py geocode_markets    # refines market pins from OpenStreetMap
python manage.py fetch_images       # downloads real photos (up to 4K) from Wikimedia Commons
python manage.py sync_hotels        # finds real hotels near every market (OpenStreetMap)
python manage.py createsuperuser
python manage.py runserver
```

Open http://127.0.0.1:8000. The admin (manage markets, products, orders) is at http://127.0.0.1:8000/admin/.

## How it works

| Feature | Where |
|---|---|
| Markets (name, 中文 name, building photo, specialty, booths, hours) | `/markets/` |
| Products linked to the markets that sell them | `/products/` |
| **Locked** market location (address, Chinese taxi address, map, Amap/Google links, transit, insider tips) | market page, unlocked by a Location Pass |
| Sourcing request ($50) with freight choice (sea LCL/FCL, air, express, own forwarder) | `/source/new/` |
| Order tracking: Paid → Sourcing → Quoted → Shipped → Delivered | `/accounts/dashboard/` |
| Location Passes: Explorer $29 / 7 days, Trader $79 / 30 days, Partner $490 / year | `/pricing/` |
| Shipping info + freight cost estimator (sea / air / express) | `/shipping/` |
| Hotels near each market, with Trip.com & Booking.com links (dates + guests pre-filled) | `/hotels/`, every market page |
| Trip planner: pick city, markets, dates → day-by-day itinerary + closest hotels | `/trip-planner/` |
| Bookable services: interpreter, factory audit, QC inspection, airport pickup, visa letter, hotel concierge… | `/services/` |
| Map of all markets (exact pins for pass holders, city-level for everyone else) | `/atlas/` |
| Saved markets, trip plans, service bookings | `/accounts/dashboard/` |

Staff work orders in the admin: change the status, add the quotation, shipping quote, tracking number and notes,
and the customer sees them on their order page. Staff accounts always see market locations.

Location data is never sent to a browser without access. It isn't hidden with CSS; the server leaves it out of the page.

## Markets

122 real wholesale markets across 19 provinces ship with the project (`catalog/data.py`).
Add hundreds more without code:

```bash
python manage.py import_markets my_markets.csv
```

CSV columns: `name, name_zh, city, province, categories, specialty, summary, description, address, address_zh,
latitude, longitude, opening_hours, booths, image_query` (only name, city, province are required;
`categories` is space-separated slugs such as `apparel bags`). You can also add markets one at a time in the admin.

**Locations are approximate until verified.** `geocode_markets` refines pins from OpenStreetMap, but before selling
Location Passes have your team confirm each one and tick **Location verified** in the admin (there's a bulk action).
Customers see a "Verified by our team" or "Approximate" badge.

## Hotels (automatic)

`python manage.py sync_hotels` asks OpenStreetMap for hotels within 2.5 km of every market, keeps the best 8
(English names, brands and star ratings first), and links them to the market with the distance. Schedule it so new
hotels appear on their own, for example weekly with cron:

```
0 3 * * 1  cd /path/to/sinosource && .venv/bin/python manage.py sync_hotels
```

- Hotels your team adds in the admin are never overwritten. Tick **Recommended** and add a note to pin a hotel at the top.
- Every hotel card links to **Trip.com** and **Booking.com** with the customer's dates and guests. Put your affiliate ids
  in `.env` (`TRIP_ALLIANCE_ID`, `TRIP_SID`, `BOOKING_AID`) so bookings earn you commission.
- Trip.com links are best when a city has a **Trip.com city id** (admin → Cities). Seven major cities are pre-filled.
- **Live prices inside your own site** need Trip.com's partner hotel API (requires an application and approval) or a
  similar provider. `travel/booking.py` is the place to plug one in once you have access.
- OpenStreetMap coverage in China varies by city. Where few hotels are mapped, pages fall back to a city-wide
  Trip.com / Booking.com search.

### If `sync_hotels`, `geocode_markets` or `fetch_images` fail

- **403 Forbidden / 406 Not Acceptable**: the free map and photo services block requests that don't carry a real
  contact e-mail. Set `OSM_CONTACT_EMAIL=you@yourdomain.com` in `.env`. The commands refuse to run without it.
- The commands automatically switch to backup servers (other Overpass servers, then Photon) if one refuses or
  times out, and stop early instead of retrying forever.
- If every server still refuses, your network is probably blocked (VPNs and shared IPs often are). Try another
  connection. Markets already processed are kept, so you can simply re-run.
- Run `python manage.py geocode_markets --dry-run` first to preview pin changes before saving them.

## Admin tools & live chat

- **Admin → Tools** (`/admin/ops/jobrun/`): run *Refine market locations*, *Find hotels*, *Fetch photos* and
  *Import markets (CSV)* with a button. Jobs run in the background with a live log.
- On **Admin → Markets** (and Products / Categories) tick rows and use the **Action** menu to find hotels,
  refine locations or fetch photos for just those.
- **Live chat**: signed-in customers get a chat bubble on every page (and `/chat/`). Staff answer in the
  **Inbox** (`/inbox/`, also linked in the admin header with an unread badge). Customers can attach photos and
  documents. Set `SUPPORT_NOTIFY_EMAIL` to be e-mailed about new messages.
- The admin uses the site's look (`templates/admin/base_site.html`, `static/admin_theme/admin.css`).

## Photos

`python manage.py fetch_images` searches Wikimedia Commons for each market, product and category, then saves
the best landscape photo at up to 3840 px wide with the author and licence stored as credit.

- `--force` replaces existing photos; `--only markets` limits it to markets.
- If a photo isn't right, change **Image query** in the admin and re-run with `--force`, or **upload your own 4K photo**
  in the admin (an uploaded photo always wins).
- Items without a photo show an animated card with their Chinese name.

## Payments

- **Demo mode** (no Stripe key): checkout shows a "Pay" button that simulates success. For development only.
- **Live**: set `STRIPE_SECRET_KEY` (+ `STRIPE_WEBHOOK_SECRET`) in `.env`. Customers pay on Stripe Checkout.
  Add a webhook in Stripe for `checkout.session.completed` pointing at `https://YOUR-DOMAIN/webhooks/stripe/`.

Change the fee with `SOURCING_FEE` in `.env`, and pass prices in the admin.

## Before going live

Set `DJANGO_DEBUG=false`, a real `DJANGO_SECRET_KEY` and `DJANGO_ALLOWED_HOSTS`, run `python manage.py collectstatic`,
and serve `media/` and `staticfiles/` from your web server. Market coordinates and addresses are approximate (street
level), so check them before selling access.
