from django.core.cache import cache
from django.db import models

CACHE_KEY = "hub-site-settings"


class SiteSettings(models.Model):
    """Business settings editable from the hub (one row only)."""

    whatsapp_number = models.CharField(
        "WhatsApp number", max_length=30, blank=True,
        help_text="International format with country code, e.g. +86 138 0000 0000 or +234 801 234 5678.",
    )
    whatsapp_message = models.CharField(
        "WhatsApp opening message", max_length=200, blank=True,
        default="Hello Masha Imports, I'd like help sourcing a product from China.",
    )
    show_whatsapp = models.BooleanField("Show WhatsApp in the chat pop-up", default=True)
    chat_enabled = models.BooleanField("Show website chat pop-up", default=True)
    chat_greeting = models.CharField(
        max_length=200, blank=True,
        default="Ask us anything: products, markets, prices, shipping or your trip to China.",
    )
    reply_time = models.CharField(max_length=60, default="Usually replies within a few hours")
    support_email = models.EmailField(blank=True, help_text="Shown to customers as a contact address.")
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = verbose_name_plural = "site settings"

    def __str__(self):
        return "Site settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
        cache.delete(CACHE_KEY)

    @classmethod
    def load(cls):
        obj = cache.get(CACHE_KEY)
        if obj is None:
            obj, _ = cls.objects.get_or_create(pk=1)
            cache.set(CACHE_KEY, obj, 60)
        return obj

    @property
    def whatsapp_digits(self):
        return "".join(ch for ch in self.whatsapp_number if ch.isdigit())

    @property
    def whatsapp_url(self):
        from urllib.parse import quote

        if not self.whatsapp_digits:
            return ""
        text = f"?text={quote(self.whatsapp_message)}" if self.whatsapp_message else ""
        return f"https://wa.me/{self.whatsapp_digits}{text}"


def whatsapp_link(phone, text=""):
    """wa.me link for any phone number (used to message a customer)."""
    from urllib.parse import quote

    digits = "".join(ch for ch in (phone or "") if ch.isdigit())
    if len(digits) < 7:
        return ""
    return f"https://wa.me/{digits}" + (f"?text={quote(text)}" if text else "")
