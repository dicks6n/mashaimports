import math

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.text import slugify

from catalog.models import ImageMixin


def distance_km(lat1, lon1, lat2, lon2):
    """Great-circle distance between two points in km."""
    lat1, lon1, lat2, lon2 = map(math.radians, map(float, (lat1, lon1, lat2, lon2)))
    a = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(a))


class City(models.Model):
    name = models.CharField(max_length=80, unique=True)
    name_zh = models.CharField(max_length=40, blank=True)
    slug = models.SlugField(unique=True, blank=True)
    province = models.CharField(max_length=80, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    trip_city_id = models.PositiveIntegerField(
        "Trip.com city id", null=True, blank=True, help_text="From trip.com/hotels/list?city=ID — improves hotel links."
    )

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "cities"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.slug = self.slug or slugify(self.name)
        super().save(*args, **kwargs)


class Hotel(ImageMixin):
    class Source(models.TextChoices):
        MANUAL = "manual", "Added by our team"
        OSM = "osm", "OpenStreetMap (automatic)"

    name = models.CharField(max_length=200)
    name_zh = models.CharField(max_length=200, blank=True)
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name="hotels")
    address = models.CharField(max_length=255, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    stars = models.PositiveSmallIntegerField(null=True, blank=True)
    brand = models.CharField(max_length=120, blank=True)
    website = models.URLField(max_length=400, blank=True)
    phone = models.CharField(max_length=60, blank=True)
    recommended = models.BooleanField(default=False, help_text="Shown first, with a 'Recommended' badge.")
    note = models.CharField(max_length=240, blank=True, help_text="Why we recommend it (shown to customers).")
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.MANUAL)
    osm_id = models.CharField(max_length=40, blank=True, db_index=True)
    active = models.BooleanField(default=True)
    markets = models.ManyToManyField("catalog.Market", through="MarketHotel", related_name="hotels", blank=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-recommended", "-stars", "name"]

    def __str__(self):
        return f"{self.name} ({self.city})"

    @property
    def display_name(self):
        return self.name or self.name_zh


class MarketHotel(models.Model):
    market = models.ForeignKey("catalog.Market", on_delete=models.CASCADE)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE)
    distance_km = models.DecimalField(max_digits=6, decimal_places=2)

    class Meta:
        ordering = ["distance_km"]
        constraints = [models.UniqueConstraint(fields=["market", "hotel"], name="unique_market_hotel")]


class Service(models.Model):
    """Paid add-on services customers can book (interpreter, inspection…)."""

    name = models.CharField(max_length=120)
    name_zh = models.CharField(max_length=20, blank=True, help_text="One or two characters used as the card's icon.")
    slug = models.SlugField(unique=True)
    summary = models.CharField(max_length=240)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    unit = models.CharField(max_length=30, default="per order", help_text="e.g. per day, per order, per trip")
    max_quantity = models.PositiveSmallIntegerField(default=1, help_text="Allow ordering several units (e.g. days).")
    order = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("travel:service_book", args=[self.slug])


class ServiceOrder(models.Model):
    class Status(models.TextChoices):
        AWAITING_PAYMENT = "awaiting_payment", "Awaiting payment"
        CONFIRMED = "confirmed", "Paid · being arranged"
        SCHEDULED = "scheduled", "Scheduled"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="service_orders")
    service = models.ForeignKey(Service, on_delete=models.PROTECT)
    quantity = models.PositiveSmallIntegerField(default=1)
    city = models.ForeignKey(City, on_delete=models.SET_NULL, null=True, blank=True)
    market = models.ForeignKey("catalog.Market", on_delete=models.SET_NULL, null=True, blank=True)
    hotel = models.ForeignKey(Hotel, on_delete=models.SET_NULL, null=True, blank=True)
    date = models.DateField("date needed", null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    guests = models.PositiveSmallIntegerField(default=1)
    phone = models.CharField("WhatsApp / phone", max_length=40)
    details = models.TextField(blank=True)
    amount = models.DecimalField(max_digits=9, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AWAITING_PAYMENT)
    staff_notes = models.TextField(blank=True, help_text="Visible to the customer.")
    paid_at = models.DateTimeField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return f"{self.service} · {self.user}"


class TripPlan(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="trip_plans")
    city = models.ForeignKey(City, on_delete=models.CASCADE)
    markets = models.ManyToManyField("catalog.Market")
    arrival = models.DateField()
    nights = models.PositiveSmallIntegerField()
    guests = models.PositiveSmallIntegerField(default=1)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return f"{self.city} · {self.arrival} · {self.nights} nights"

    def get_absolute_url(self):
        return reverse("travel:trip_plan", args=[self.pk])
