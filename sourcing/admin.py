from django.contrib import admin

from .models import Payment, Plan, SourcingRequest, Subscription


@admin.register(SourcingRequest)
class SourcingRequestAdmin(admin.ModelAdmin):
    list_display = ["reference", "title", "user", "status", "shipping_method", "destination", "paid_at", "created"]
    list_filter = ["status", "shipping_method", "created"]
    list_editable = ["status"]
    search_fields = ["reference", "title", "user__username", "user__email", "destination"]
    readonly_fields = ["reference", "paid_at", "created", "updated"]
    autocomplete_fields = ["product", "market"]
    fieldsets = [
        ("Order", {"fields": ["reference", "user", "status", "fee", "paid_at"]}),
        ("Customer brief", {"fields": ["title", "details", "quantity", "target_price", "reference_image", "product", "market"]}),
        ("Shipping", {"fields": ["destination", "shipping_method", "shipping_quote", "tracking_number"]}),
        ("Agent response (visible to customer)", {"fields": ["quoted_price", "agent_notes"]}),
        ("Timestamps", {"fields": ["created", "updated"]}),
    ]


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ["name", "price", "duration_days", "highlighted", "active", "order"]
    list_editable = ["price", "highlighted", "active", "order"]
    prepopulated_fields = {"slug": ["name"]}


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ["user", "plan", "starts_at", "expires_at"]
    list_filter = ["plan"]
    search_fields = ["user__username", "user__email"]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "kind", "amount", "status", "provider", "created", "paid_at"]
    list_filter = ["kind", "status", "provider"]
    search_fields = ["user__username", "provider_ref"]
    readonly_fields = ["created", "paid_at"]
