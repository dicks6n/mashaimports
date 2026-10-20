from django.db import models
from django.urls import reverse
from django.utils.text import slugify


def image_upload_to(instance, filename):
    return f"{instance._meta.model_name}s/{filename}"


class ImageMixin(models.Model):
    """Shared photo fields. An uploaded file always wins over a remote URL."""

    image = models.ImageField(upload_to=image_upload_to, blank=True)
    image_url = models.URLField(
        max_length=600, blank=True, help_text="Optional remote photo, used when no file is uploaded."
    )
    image_credit = models.CharField(max_length=300, blank=True)
    image_source = models.URLField(max_length=600, blank=True)
    image_query = models.CharField(
        max_length=200,
        blank=True,
        help_text="Search phrase used by `python manage.py fetch_images` on Wikimedia Commons.",
    )

    class Meta:
        abstract = True

    @property
    def image_src(self):
        if self.image:
            return self.image.url
        return self.image_url


class Category(ImageMixin):
    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True, blank=True)
    tagline = models.CharField(max_length=200, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.slug = self.slug or slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("catalog:product_list") + f"?category={self.slug}"


class Market(ImageMixin):
    name = models.CharField(max_length=160)
    name_zh = models.CharField("Chinese name", max_length=80, blank=True)
    slug = models.SlugField(unique=True, blank=True)
    city = models.CharField(max_length=80)
    province = models.CharField(max_length=80)
    specialty = models.CharField(max_length=160, help_text="What the market is known for.")
    summary = models.CharField(max_length=260)
    description = models.TextField()
    established = models.PositiveIntegerField(null=True, blank=True)
    booths = models.PositiveIntegerField("approx. booths / shops", null=True, blank=True)
    opening_hours = models.CharField(max_length=120, blank=True)
    featured = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    categories = models.ManyToManyField("Category", related_name="markets", blank=True)

    # --- Premium fields: only shown to subscribers -------------------------
    address = models.CharField(max_length=255, blank=True)
    address_zh = models.CharField("address (Chinese)", max_length=255, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    nearest_transit = models.CharField(max_length=200, blank=True)
    insider_tips = models.TextField(blank=True, help_text="Premium buying tips for subscribers.")
    location_verified = models.BooleanField(
        default=False, help_text="Tick once your team has confirmed the address and pin on the ground."
    )

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.slug = self.slug or slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("catalog:market_detail", args=[self.slug])

    @property
    def has_coordinates(self):
        return self.latitude is not None and self.longitude is not None

    @property
    def map_embed_url(self):
        if not self.has_coordinates:
            return ""
        lat, lon, d = float(self.latitude), float(self.longitude), 0.006
        return (
            "https://www.openstreetmap.org/export/embed.html"
            f"?bbox={lon - d}%2C{lat - d}%2C{lon + d}%2C{lat + d}"
            f"&layer=mapnik&marker={lat}%2C{lon}"
        )

    @property
    def google_maps_url(self):
        if not self.has_coordinates:
            return ""
        return f"https://www.google.com/maps/search/?api=1&query={self.latitude},{self.longitude}"

    @property
    def amap_url(self):
        """Amap (Gaode) works inside mainland China where Google Maps does not."""
        if not self.has_coordinates:
            return ""
        return f"https://uri.amap.com/marker?position={self.longitude},{self.latitude}&name={self.name_zh or self.name}"


class Product(ImageMixin):
    name = models.CharField(max_length=160)
    slug = models.SlugField(unique=True, blank=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    markets = models.ManyToManyField(Market, related_name="products", blank=True)
    summary = models.CharField(max_length=260)
    description = models.TextField(blank=True)
    price_from = models.DecimalField("factory price from (USD)", max_digits=10, decimal_places=2)
    price_to = models.DecimalField("factory price to (USD)", max_digits=10, decimal_places=2)
    moq = models.CharField("minimum order", max_length=60, blank=True)
    lead_time = models.CharField(max_length=60, blank=True)
    featured = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-featured", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.slug = self.slug or slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("catalog:product_detail", args=[self.slug])


class Favorite(models.Model):
    user = models.ForeignKey("auth.User", on_delete=models.CASCADE, related_name="favorites")
    market = models.ForeignKey(Market, on_delete=models.CASCADE, related_name="favorited_by")
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created"]
        constraints = [models.UniqueConstraint(fields=["user", "market"], name="unique_favorite")]
