from django.contrib import admin

from catalog.admin import PHOTO_FIELDS, thumb

from .models import City, Hotel, MarketHotel, Service, ServiceOrder, TripPlan


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ["name", "name_zh", "province", "trip_city_id"]
    list_editable = ["trip_city_id"]
    search_fields = ["name", "name_zh"]
    prepopulated_fields = {"slug": ["name"]}


class MarketHotelInline(admin.TabularInline):
    model = MarketHotel
    extra = 0
    autocomplete_fields = ["market"]


@admin.register(Hotel)
class HotelAdmin(admin.ModelAdmin):
    list_display = [thumb, "name", "name_zh", "city", "stars", "recommended", "source", "active"]
    list_editable = ["recommended", "active"]
    list_filter = ["recommended", "source", "stars", "city"]
    search_fields = ["name", "name_zh", "brand", "address"]
    inlines = [MarketHotelInline]
    fieldsets = [
        (None, {"fields": ["name", "name_zh", "city", "brand", "stars", "address", "latitude", "longitude"]}),
        ("Recommendation", {"fields": ["recommended", "note", "active"]}),
        ("Contact", {"fields": ["website", "phone"]}),
        ("Source", {"fields": ["source", "osm_id"]}),
        PHOTO_FIELDS,
    ]


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ["name", "price", "unit", "max_quantity", "active", "order"]
    list_editable = ["price", "active", "order"]
    prepopulated_fields = {"slug": ["name"]}


@admin.register(ServiceOrder)
class ServiceOrderAdmin(admin.ModelAdmin):
    list_display = ["service", "user", "quantity", "city", "date", "amount", "status", "paid_at"]
    list_filter = ["status", "service", "city"]
    list_editable = ["status"]
    search_fields = ["user__username", "user__email", "phone", "details"]
    readonly_fields = ["amount", "paid_at", "created"]


@admin.register(TripPlan)
class TripPlanAdmin(admin.ModelAdmin):
    list_display = ["user", "city", "arrival", "nights", "guests", "created"]
    list_filter = ["city"]
    filter_horizontal = ["markets"]
