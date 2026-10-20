import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models, transaction
from django.urls import reverse
from django.utils import timezone


class Plan(models.Model):
    """A paid pass that unlocks market addresses, maps and insider tips."""

    name = models.CharField(max_length=80)
    slug = models.SlugField(unique=True)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    duration_days = models.PositiveIntegerField()
    tagline = models.CharField(max_length=160, blank=True)
    features = models.TextField(help_text="One feature per line.")
    highlighted = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "price"]

    def __str__(self):
        return f"{self.name} (${self.price})"

    @property
    def feature_list(self):
        return [f.strip() for f in self.features.splitlines() if f.strip()]


class Subscription(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="subscriptions")
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)
    starts_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-expires_at"]

    def __str__(self):
        return f"{self.user} · {self.plan.name} until {self.expires_at:%Y-%m-%d}"

    @property
    def is_active(self):
        return self.starts_at <= timezone.now() < self.expires_at

    @classmethod
    def current_for(cls, user):
        if not user.is_authenticated:
            return None
        now = timezone.now()
        return cls.objects.filter(user=user, starts_at__lte=now, expires_at__gt=now).first()


def has_location_access(user):
    return user.is_authenticated and (user.is_staff or Subscription.current_for(user) is not None)


def _new_reference():
    return "SS-" + secrets.token_hex(3).upper()


class SourcingRequest(models.Model):
    class Status(models.TextChoices):
        AWAITING_PAYMENT = "awaiting_payment", "Awaiting payment"
        PAID = "paid", "Paid · queued"
        SOURCING = "sourcing", "Agent sourcing in market"
        QUOTED = "quoted", "Quotation ready"
        SHIPPING = "shipping", "Shipped · in transit"
        COMPLETED = "completed", "Delivered"
        CANCELLED = "cancelled", "Cancelled"

    class ShippingMethod(models.TextChoices):
        ADVISE = "advise", "Advise me (cheapest reliable route)"
        SEA_LCL = "sea_lcl", "Sea freight · shared container (LCL)"
        SEA_FCL = "sea_fcl", "Sea freight · full container (FCL)"
        AIR = "air", "Air cargo"
        EXPRESS = "express", "Express courier (DHL / FedEx / UPS)"
        PICKUP = "pickup", "I have my own forwarder"

    reference = models.CharField(max_length=12, unique=True, default=_new_reference, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sourcing_requests")
    product = models.ForeignKey("catalog.Product", on_delete=models.SET_NULL, null=True, blank=True)
    market = models.ForeignKey("catalog.Market", on_delete=models.SET_NULL, null=True, blank=True)
    title = models.CharField("what should we source?", max_length=200)
    details = models.TextField(help_text="Specs, materials, colours, packaging, branding…")
    quantity = models.CharField(max_length=60)
    target_price = models.CharField("target unit price", max_length=60, blank=True)
    destination = models.CharField("ship to (country / city)", max_length=120)
    shipping_method = models.CharField(max_length=20, choices=ShippingMethod.choices, default=ShippingMethod.ADVISE)
    shipping_quote = models.CharField(max_length=160, blank=True, help_text="Freight cost / ETA given to the customer.")
    tracking_number = models.CharField(max_length=80, blank=True)
    reference_image = models.ImageField(upload_to="requests/", blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AWAITING_PAYMENT)
    fee = models.DecimalField(max_digits=8, decimal_places=2, default=settings.SOURCING_FEE)
    paid_at = models.DateTimeField(null=True, blank=True)
    quoted_price = models.CharField(max_length=120, blank=True)
    agent_notes = models.TextField(blank=True, help_text="Visible to the customer on their dashboard.")
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return f"{self.reference} · {self.title}"

    def get_absolute_url(self):
        return reverse("sourcing:request_detail", args=[self.reference])

    @property
    def is_paid(self):
        return self.paid_at is not None

    @property
    def progress_step(self):
        order = ["awaiting_payment", "paid", "sourcing", "quoted", "shipping", "completed"]
        return order.index(self.status) if self.status in order else 0


class Payment(models.Model):
    class Kind(models.TextChoices):
        SOURCING = "sourcing", "Sourcing fee"
        SUBSCRIPTION = "subscription", "Location pass"
        SERVICE = "service", "Service booking"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="payments")
    kind = models.CharField(max_length=20, choices=Kind.choices)
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    currency = models.CharField(max_length=3, default="usd")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    provider = models.CharField(max_length=20, default="stripe")
    provider_ref = models.CharField(max_length=255, blank=True, db_index=True)
    sourcing_request = models.ForeignKey(SourcingRequest, on_delete=models.SET_NULL, null=True, blank=True)
    plan = models.ForeignKey(Plan, on_delete=models.SET_NULL, null=True, blank=True)
    service_order = models.ForeignKey("travel.ServiceOrder", on_delete=models.SET_NULL, null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return f"{self.get_kind_display()} · ${self.amount} · {self.status}"

    @property
    def description(self):
        if self.kind == self.Kind.SOURCING and self.sourcing_request:
            return f"Sourcing fee · {self.sourcing_request.title}"
        if self.service_order:
            o = self.service_order
            qty = f" × {o.quantity}" if o.quantity > 1 else ""
            return f"{o.service.name}{qty}"
        if self.plan:
            return f"{self.plan.name} · {self.plan.duration_days}-day market location pass"
        return self.get_kind_display()

    def mark_paid(self):
        """Idempotently mark this payment paid and deliver what was bought."""
        with transaction.atomic():
            payment = Payment.objects.select_for_update().get(pk=self.pk)
            if payment.status == self.Status.PAID:
                return payment
            now = timezone.now()
            payment.status = self.Status.PAID
            payment.paid_at = now
            payment.save(update_fields=["status", "paid_at"])

            if payment.kind == self.Kind.SOURCING and payment.sourcing_request:
                req = payment.sourcing_request
                req.paid_at = now
                req.status = SourcingRequest.Status.PAID
                req.save(update_fields=["paid_at", "status", "updated"])
            elif payment.kind == self.Kind.SUBSCRIPTION and payment.plan:
                # Stack on top of an existing pass instead of overlapping it.
                current = Subscription.current_for(payment.user)
                start = current.expires_at if current else now
                Subscription.objects.create(
                    user=payment.user,
                    plan=payment.plan,
                    starts_at=start,
                    expires_at=start + timedelta(days=payment.plan.duration_days),
                )
            elif payment.kind == self.Kind.SERVICE and payment.service_order:
                order = payment.service_order
                order.paid_at = now
                order.status = "confirmed"
                order.save(update_fields=["paid_at", "status"])
        self.refresh_from_db()
        return self
