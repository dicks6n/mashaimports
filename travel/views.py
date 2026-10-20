from datetime import timedelta

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from catalog.models import Market
from sourcing import payments
from sourcing.models import Payment, has_location_access

from . import booking
from .forms import ServiceOrderForm, TripPlanForm, parse_stay
from .models import City, Hotel, Service, ServiceOrder, TripPlan, distance_km


def _with_links(hotels, checkin, checkout, guests):
    for h in hotels:
        h.links = booking.links_for(h, checkin, checkout, guests)
    return hotels


def hotel_list(request):
    checkin, checkout, guests = parse_stay(request.GET)
    hotels = Hotel.objects.filter(active=True).select_related("city")
    city = City.objects.filter(slug=request.GET.get("city", "")).first()
    market = Market.objects.filter(slug=request.GET.get("market", "")).first()
    q = request.GET.get("q", "").strip()

    if market:
        hotels = hotels.filter(markethotel__market=market).order_by(
            "-recommended", "markethotel__distance_km"
        )
        city = city or City.objects.filter(name=market.city).first()
    elif city:
        hotels = hotels.filter(city=city)
    if q:
        hotels = hotels.filter(Q(name__icontains=q) | Q(name_zh__icontains=q) | Q(brand__icontains=q))

    page = Paginator(hotels if market else hotels.distinct(), 18).get_page(request.GET.get("page"))
    _with_links(page.object_list, checkin, checkout, guests)
    if market:
        dist = dict(market.markethotel_set.values_list("hotel_id", "distance_km"))
        for h in page.object_list:
            h.distance = dist.get(h.pk)

    cities = City.objects.annotate(n=Count("hotels")).filter(n__gt=0)
    city_links = booking.links_for(city, checkin, checkout, guests) if city else None
    return render(request, "travel/hotel_list.html", {
        "page": page, "cities": cities, "city": city, "market": market, "q": q,
        "checkin": checkin, "checkout": checkout, "guests": guests, "city_links": city_links,
        "all_cities": City.objects.all(),
    })


def trip_planner(request):
    initial = {}
    if request.GET.get("market"):
        m = Market.objects.filter(slug=request.GET["market"]).first()
        if m:
            initial = {"city": City.objects.filter(name=m.city).first(), "markets": [m]}
    form = TripPlanForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        markets = d["markets"] or list(
            Market.objects.filter(city=d["city"].name).annotate(n=Count("products")).order_by("-featured", "-n")[:4]
        )
        if request.user.is_authenticated:
            plan = TripPlan.objects.create(
                user=request.user, city=d["city"], arrival=d["arrival"], nights=d["nights"], guests=d["guests"]
            )
            plan.markets.set(markets)
            return redirect(plan)
        return render(request, "travel/trip_plan.html",
                      _build_plan(request, d["city"], markets, d["arrival"], d["nights"], d["guests"]))

    markets_by_city = {}
    for m in Market.objects.order_by("city", "name").values("id", "name", "name_zh", "city"):
        markets_by_city.setdefault(m["city"], []).append(m)
    return render(request, "travel/trip_planner.html", {
        "form": form, "markets_by_city": markets_by_city,
        "selected": [str(m.pk) for m in initial.get("markets", [])] or request.POST.getlist("markets"),
    })


@login_required
def trip_plan(request, pk):
    plan = get_object_or_404(TripPlan, pk=pk, user=request.user)
    ctx = _build_plan(request, plan.city, list(plan.markets.all()), plan.arrival, plan.nights, plan.guests)
    ctx["plan"] = plan
    return render(request, "travel/trip_plan.html", ctx)


def _build_plan(request, city, markets, arrival, nights, guests):
    checkout = arrival + timedelta(days=nights)
    # Spread markets across the full days (arrival day is for check-in).
    full_days = max(1, nights - 1) if nights > 1 else 1
    days = []
    per_day = max(1, -(-len(markets) // full_days))  # ceil
    for i in range(full_days):
        chunk = markets[i * per_day:(i + 1) * per_day]
        days.append({"date": arrival + timedelta(days=i + (1 if nights > 1 else 0)), "markets": chunk})

    # Hotels ranked by average distance to the chosen markets.
    pins = [m for m in markets if m.has_coordinates]
    hotels = list(Hotel.objects.filter(active=True, city=city))
    for h in hotels:
        h.avg_km = (sum(distance_km(m.latitude, m.longitude, h.latitude, h.longitude) for m in pins) / len(pins)) if pins else None
    hotels.sort(key=lambda h: (not h.recommended, h.avg_km if h.avg_km is not None else 999, -(h.stars or 0)))
    hotels = _with_links(hotels[:6], arrival, checkout, guests)

    return {
        "city": city, "markets": markets, "arrival": arrival, "checkout": checkout, "nights": nights,
        "guests": guests, "days": days, "hotels": hotels,
        "city_links": booking.links_for(city, arrival, checkout, guests),
        "services": Service.objects.filter(active=True, slug__in=[
            "interpreter", "airport-pickup", "hotel-booking", "factory-audit", "visa-letter"]),
    }


def service_list(request):
    return render(request, "travel/service_list.html", {"services": Service.objects.filter(active=True)})


@login_required
def service_book(request, slug):
    service = get_object_or_404(Service, slug=slug, active=True)
    initial = {"quantity": 1}
    for field, model in (("city", City), ("market", Market), ("hotel", Hotel)):
        val = request.GET.get(field)
        if val:
            obj = model.objects.filter(**({"pk": val} if field == "hotel" else {"slug": val})).first()
            if obj:
                initial[field] = obj
    if "hotel" in initial and "city" not in initial:
        initial["city"] = initial["hotel"].city
    if "market" in initial and "city" not in initial:
        initial["city"] = City.objects.filter(name=initial["market"].city).first()
    if request.GET.get("checkin"):
        initial["date"] = request.GET["checkin"]
        initial["end_date"] = request.GET.get("checkout")

    form = ServiceOrderForm(request.POST or None, initial=initial, service=service)
    if request.method == "POST" and form.is_valid():
        order = form.save(commit=False)
        order.user = request.user
        order.service = service
        order.hotel = initial.get("hotel")
        order.amount = service.price * order.quantity
        order.save()
        payment = Payment.objects.create(
            user=request.user, kind=Payment.Kind.SERVICE, amount=order.amount,
            currency=settings.CURRENCY, service_order=order,
        )
        return payments.start_checkout(request, payment)
    return render(request, "travel/service_book.html", {"service": service, "form": form, "hotel": initial.get("hotel")})


def atlas(request):
    """All markets on one map. Exact pins for pass holders, city-level otherwise."""
    access = has_location_access(request.user)
    markets = Market.objects.exclude(latitude=None)
    if access:
        points = [{"name": m.name, "zh": m.name_zh, "city": m.city, "spec": m.specialty, "url": m.get_absolute_url(),
                   "lat": float(m.latitude), "lon": float(m.longitude)} for m in markets]
    else:
        groups = {}
        for m in markets:
            groups.setdefault(m.city, []).append(m)
        points = []
        for name, ms in groups.items():
            c = City.objects.filter(name=name).first()
            lat = float(c.latitude) if c and c.latitude else float(ms[0].latitude)
            lon = float(c.longitude) if c and c.longitude else float(ms[0].longitude)
            points.append({"city": name, "count": len(ms), "lat": round(lat, 1), "lon": round(lon, 1),
                           "names": [m.name for m in ms][:8]})
    provinces = markets.values("province").annotate(n=Count("id")).order_by("-n")
    return render(request, "travel/atlas.html", {
        "points": points, "access": access, "total": markets.count(), "provinces": provinces,
    })
