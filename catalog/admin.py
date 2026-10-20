from django.contrib import admin
from django.utils.html import format_html

from ops.admin import fetch_photos_action_for, find_hotels_action, geocode_action

from .models import Category, Market, Product


def thumb(obj):
    if obj.image_src:
        return format_html('<img src="{}" style="height:48px;width:72px;object-fit:cover;border-radius:4px">', obj.image_src)
    return "—"


thumb.short_description = "Photo"

PHOTO_FIELDS = ("Photo", {"fields": ["image", "image_url", "image_credit", "image_source", "image_query"]})


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = [thumb, "name", "tagline", "order"]
    list_editable = ["order"]
    prepopulated_fields = {"slug": ["name"]}
    actions = [fetch_photos_action_for("categories")]


@admin.register(Market)
class MarketAdmin(admin.ModelAdmin):
    list_display = [thumb, "name", "name_zh", "city", "province", "specialty", "featured", "location_verified"]
    list_editable = ["featured", "location_verified"]
    list_filter = ["location_verified", "featured", "province", "categories", "city"]
    filter_horizontal = ["categories"]
    actions = ["mark_verified", find_hotels_action, geocode_action, fetch_photos_action_for("markets")]
    search_fields = ["name", "name_zh", "city", "specialty"]
    prepopulated_fields = {"slug": ["name"]}
    fieldsets = [
        (None, {"fields": ["name", "name_zh", "slug", "city", "province", "categories", "specialty", "summary", "description"]}),
        ("Facts", {"fields": ["established", "booths", "opening_hours", "featured", "order"]}),
        ("Premium · location (subscribers only)", {
            "fields": ["address", "address_zh", "latitude", "longitude", "location_verified", "nearest_transit", "insider_tips"]
        }),
        PHOTO_FIELDS,
    ]

    @admin.action(description="Mark location as verified")
    def mark_verified(self, request, queryset):
        n = queryset.update(location_verified=True)
        self.message_user(request, f"{n} market(s) marked verified.")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [thumb, "name", "category", "price_from", "price_to", "moq", "featured"]
    list_editable = ["featured"]
    list_filter = ["category", "featured", "markets"]
    search_fields = ["name", "summary"]
    prepopulated_fields = {"slug": ["name"]}
    filter_horizontal = ["markets"]
    actions = [fetch_photos_action_for("products")]
    fieldsets = [
        (None, {"fields": ["name", "slug", "category", "markets", "summary", "description", "featured"]}),
        ("Trade terms", {"fields": ["price_from", "price_to", "moq", "lead_time"]}),
        PHOTO_FIELDS,
    ]
