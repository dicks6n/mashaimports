"""List/edit configuration for the hub's catalogue screens.

Each Resource tells the generic list and form views how to show one model:
which columns, what to search, which quick filters and how to group the form.
"""

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Tuple

from django.db.models import Count, Q
from django.utils.html import format_html

from catalog.models import Category, Market, Product
from sourcing.models import Plan
from travel.models import City, Hotel, Service

from . import forms


def thumb(obj):
    src = obj.image_src
    if src:
        return format_html('<img class="hub-thumb" src="{}" alt="" loading="lazy">', src)
    return format_html('<span class="hub-thumb hub-thumb-empty">{}</span>', (getattr(obj, "name_zh", "") or obj.name)[:2])


def name_cell(obj):
    zh = getattr(obj, "name_zh", "")
    return format_html("<b>{}</b>{}", obj.name, format_html('<small class="zh">{}</small>', zh) if zh else "")


def yes(value, on="Yes", off="—", tone="good"):
    if value:
        return format_html('<span class="hub-pill {}">{}</span>', tone, on)
    return format_html('<span class="hub-muted">{}</span>', off)


def money(value):
    return format_html("${}", f"{value:,.2f}")


@dataclass
class Resource:
    key: str
    model: type
    form_class: type
    title: str
    singular: str
    columns: List[Tuple[str, Callable]]
    search: List[str]
    fieldsets: List[Tuple[str, List[str]]]
    order_by: Tuple[str, ...] = ("name",)
    filters: Dict[str, Tuple[str, Q]] = field(default_factory=dict)
    annotate: Dict[str, object] = field(default_factory=dict)
    select_related: Tuple[str, ...] = ()
    icon: str = "·"
    public_url: bool = False  # objects have get_absolute_url on the public site

    def queryset(self):
        qs = self.model.objects.all()
        if self.select_related:
            qs = qs.select_related(*self.select_related)
        if self.annotate:
            qs = qs.annotate(**self.annotate)
        return qs.order_by(*self.order_by)


PHOTO_SET = ("Photo", ["image", "image_url", "image_credit", "image_source", "image_query"])

RESOURCES = {
    r.key: r
    for r in [
        Resource(
            key="markets", model=Market, form_class=forms.MarketForm, title="Markets", singular="market", icon="市",
            columns=[
                ("", thumb), ("Market", name_cell),
                ("City", lambda m: f"{m.city}, {m.province}"),
                ("Hotels", lambda m: m.hotel_count),
                ("Location", lambda m: yes(m.location_verified, "Verified", "Approximate")),
                ("Featured", lambda m: yes(m.featured, "★ Featured", "—", "gold")),
            ],
            search=["name", "name_zh", "city", "province", "specialty"],
            order_by=("order", "name"),
            annotate={"hotel_count": Count("hotels", distinct=True)},
            filters={
                "unverified": ("Unverified location", Q(location_verified=False)),
                "nophoto": ("No photo", Q(image="") & Q(image_url="")),
                "nohotels": ("No hotels", Q(hotels=None)),
                "featured": ("Featured", Q(featured=True)),
            },
            fieldsets=[
                ("Market", ["name", "name_zh", "city", "province", "specialty", "summary", "description", "categories"]),
                ("Facts", ["established", "booths", "opening_hours", "featured", "order"]),
                ("Location (Location Pass holders only)", ["address", "address_zh", "latitude", "longitude",
                                                          "location_verified", "nearest_transit", "insider_tips"]),
                PHOTO_SET,
            ],
            public_url=True,
        ),
        Resource(
            key="products", model=Product, form_class=forms.ProductForm, title="Products", singular="product", icon="品",
            columns=[
                ("", thumb), ("Product", name_cell),
                ("Category", lambda p: p.category.name),
                ("Price", lambda p: f"${p.price_from:,.2f} – ${p.price_to:,.2f}"),
                ("Markets", lambda p: p.market_count),
                ("Featured", lambda p: yes(p.featured, "★ Featured", "—", "gold")),
            ],
            search=["name", "summary", "category__name"],
            order_by=("-featured", "name"),
            select_related=("category",),
            annotate={"market_count": Count("markets", distinct=True)},
            filters={"nophoto": ("No photo", Q(image="") & Q(image_url="")), "featured": ("Featured", Q(featured=True))},
            fieldsets=[
                ("Product", ["name", "category", "summary", "description", "featured"]),
                ("Trade terms", ["price_from", "price_to", "moq", "lead_time"]),
                ("Sold in these markets", ["markets"]),
                PHOTO_SET,
            ],
            public_url=True,
        ),
        Resource(
            key="categories", model=Category, form_class=forms.CategoryForm, title="Categories", singular="category", icon="类",
            columns=[("", thumb), ("Category", name_cell), ("Tagline", lambda c: c.tagline), ("Products", lambda c: c.product_count)],
            search=["name", "tagline"], order_by=("order", "name"),
            annotate={"product_count": Count("products", distinct=True)},
            fieldsets=[("Category", ["name", "tagline", "order"]), PHOTO_SET],
        ),
        Resource(
            key="hotels", model=Hotel, form_class=forms.HotelForm, title="Hotels", singular="hotel", icon="宿",
            columns=[
                ("", thumb), ("Hotel", name_cell), ("City", lambda h: h.city.name),
                ("Stars", lambda h: "★" * (h.stars or 0) or "—"),
                ("Near", lambda h: f"{h.market_count} market(s)"),
                ("Recommended", lambda h: yes(h.recommended, "★ Recommended", "—", "gold")),
                ("Source", lambda h: h.get_source_display()),
                ("Shown", lambda h: yes(h.active, "Live", "Hidden")),
            ],
            search=["name", "name_zh", "brand", "city__name", "address"],
            order_by=("-recommended", "city__name", "name"),
            select_related=("city",),
            annotate={"market_count": Count("markets", distinct=True)},
            filters={
                "recommended": ("Recommended", Q(recommended=True)),
                "manual": ("Added by us", Q(source="manual")),
                "hidden": ("Hidden", Q(active=False)),
            },
            fieldsets=[
                ("Hotel", ["name", "name_zh", "city", "brand", "stars", "address", "latitude", "longitude"]),
                ("Recommendation", ["recommended", "note", "active"]),
                ("Contact", ["website", "phone"]),
                ("Photo", ["image", "image_url", "image_credit"]),
            ],
        ),
        Resource(
            key="cities", model=City, form_class=forms.CityForm, title="Cities", singular="city", icon="城",
            columns=[("City", name_cell), ("Province", lambda c: c.province), ("Hotels", lambda c: c.hotel_count),
                     ("Trip.com id", lambda c: c.trip_city_id or "—")],
            search=["name", "name_zh", "province"],
            annotate={"hotel_count": Count("hotels", distinct=True)},
            fieldsets=[("City", ["name", "name_zh", "province", "latitude", "longitude", "trip_city_id"])],
        ),
        Resource(
            key="services", model=Service, form_class=forms.ServiceForm, title="Services & prices", singular="service", icon="务",
            columns=[("", lambda s: format_html('<span class="hub-zh-icon">{}</span>', s.name_zh)), ("Service", lambda s: format_html("<b>{}</b>", s.name)),
                     ("Price", lambda s: f"${s.price:,.0f} {s.unit}"), ("Live", lambda s: yes(s.active, "Live", "Hidden"))],
            search=["name", "summary"], order_by=("order", "name"),
            fieldsets=[("Service", ["name", "name_zh", "slug", "summary", "description"]),
                       ("Pricing", ["price", "unit", "max_quantity"]), ("Display", ["order", "active"])],
        ),
        Resource(
            key="plans", model=Plan, form_class=forms.PlanForm, title="Location passes", singular="pass", icon="证",
            columns=[("Pass", lambda p: format_html("<b>{}</b>", p.name)), ("Price", lambda p: money(p.price)),
                     ("Length", lambda p: f"{p.duration_days} days"),
                     ("Highlighted", lambda p: yes(p.highlighted, "Highlighted", "—", "gold")),
                     ("Live", lambda p: yes(p.active, "Live", "Hidden"))],
            search=["name"], order_by=("order", "price"),
            fieldsets=[("Pass", ["name", "slug", "tagline", "features"]),
                       ("Pricing", ["price", "duration_days"]), ("Display", ["highlighted", "order", "active"])],
        ),
    ]
}
