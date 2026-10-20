from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from travel import booking
from travel.forms import parse_stay
from travel.models import City, Hotel, Service

from .models import Category, Favorite, Market, Product


def _favorite_ids(user):
    return set(user.favorites.values_list("market_id", flat=True)) if user.is_authenticated else set()


def home(request):
    markets = Market.objects.annotate(product_count=Count("products"))
    hero_markets = [m for m in markets if m.image_src][:6]
    return render(
        request,
        "catalog/home.html",
        {
            "hero_markets": hero_markets,
            "featured_markets": markets.filter(featured=True)[:6],
            "favorite_ids": _favorite_ids(request.user),
            "all_markets": markets.filter(Q(featured=True) | Q(order__lt=40)),
            "categories": Category.objects.annotate(product_count=Count("products")),
            "featured_products": Product.objects.filter(featured=True).select_related("category")[:8],
            "services": Service.objects.filter(active=True)[:6],
            "hotel_count": Hotel.objects.filter(active=True).count(),
            "city_count": City.objects.count(),
            "province_count": markets.values("province").distinct().count(),
            "stats": {
                "markets": markets.count(),
                "products": Product.objects.count(),
                "booths": sum(m.booths or 0 for m in markets),
            },
        },
    )


def market_list(request):
    markets = Market.objects.annotate(product_count=Count("products", distinct=True)).order_by("order", "name")
    q = request.GET.get("q", "").strip()
    city = request.GET.get("city", "").strip()
    province = request.GET.get("province", "").strip()
    category = Category.objects.filter(slug=request.GET.get("category", "")).first()
    if q:
        markets = markets.filter(
            Q(name__icontains=q) | Q(name_zh__icontains=q) | Q(specialty__icontains=q)
            | Q(city__icontains=q) | Q(products__name__icontains=q)
        ).distinct()
    if city:
        markets = markets.filter(city__iexact=city)
    if province:
        markets = markets.filter(province__iexact=province)
    if category:
        markets = markets.filter(categories=category)

    page = Paginator(markets, 24).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    return render(request, "catalog/market_list.html", {
        "page": page, "markets": page.object_list, "total": page.paginator.count,
        "q": q, "city": city, "province": province, "active_category": category,
        "cities": Market.objects.order_by("city").values_list("city", flat=True).distinct(),
        "provinces": Market.objects.order_by("province").values_list("province", flat=True).distinct(),
        "categories": Category.objects.annotate(n=Count("markets")).filter(n__gt=0),
        "querystring": params.urlencode(), "favorite_ids": _favorite_ids(request.user),
    })


def market_detail(request, slug):
    market = get_object_or_404(Market, slug=slug)
    products = market.products.select_related("category")
    others = Market.objects.exclude(pk=market.pk).filter(city=market.city)[:3]

    checkin, checkout, guests = parse_stay(request.GET)
    links = market.markethotel_set.select_related("hotel__city").filter(hotel__active=True)
    links = sorted(links, key=lambda mh: (not mh.hotel.recommended, mh.distance_km))[:6]
    hotels = []
    for mh in links:
        h = mh.hotel
        h.distance = mh.distance_km
        h.links = booking.links_for(h, checkin, checkout, guests)
        hotels.append(h)
    city = City.objects.filter(name=market.city).first()
    return render(request, "catalog/market_detail.html", {
        "market": market, "products": products, "others": others, "hotels": hotels, "city": city,
        "city_links": booking.links_for(city, checkin, checkout, guests) if city else None,
        "checkin": checkin, "checkout": checkout, "guests": guests,
        "is_favorite": market.pk in _favorite_ids(request.user),
        "favorite_ids": _favorite_ids(request.user),
    })


@login_required
@require_POST
def toggle_favorite(request, slug):
    market = get_object_or_404(Market, slug=slug)
    fav, created = Favorite.objects.get_or_create(user=request.user, market=market)
    if not created:
        fav.delete()
    nxt = request.POST.get("next", "")
    if url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        return redirect(nxt)
    return redirect(market)


def product_list(request):
    products = Product.objects.select_related("category").prefetch_related("markets")
    q = request.GET.get("q", "").strip()
    category = Category.objects.filter(slug=request.GET.get("category", "")).first()
    if q:
        products = products.filter(
            Q(name__icontains=q) | Q(summary__icontains=q) | Q(category__name__icontains=q)
        ).distinct()
    if category:
        products = products.filter(category=category)
    return render(
        request,
        "catalog/product_list.html",
        {"products": products, "categories": Category.objects.all(), "active_category": category, "q": q},
    )


def product_detail(request, slug):
    product = get_object_or_404(Product.objects.select_related("category"), slug=slug)
    related = Product.objects.filter(category=product.category).exclude(pk=product.pk)[:4]
    return render(
        request,
        "catalog/product_detail.html",
        {"product": product, "markets": product.markets.all(), "related": related},
    )
