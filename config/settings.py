"""
Django settings for the Masha Imports project.

Configuration is read from environment variables (or a local `.env` file).
See `.env.example` for every supported option.
"""

import os
from decimal import Decimal
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path):
    """Minimal .env loader so the project has no extra dependency for it."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).lower() in {"1", "true", "yes", "on"}


SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY", "dev-only-insecure-key-change-me-before-deploying"
)
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = [
    h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",") if h.strip()
]
CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "catalog",
    "sourcing",
    "accounts",
    "travel",
    "support",
    "ops",
    "hub",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "sourcing.context_processors.platform",
                "support.context_processors.support",
                "hub.context_processors.site_settings",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "accounts:dashboard"
LOGOUT_REDIRECT_URL = "catalog:home"

# --- Masha Imports business settings -------------------------------------------

SITE_NAME = os.environ.get("SITE_NAME", "Masha Imports")
SITE_TAGLINE = os.environ.get("SITE_TAGLINE", "Shipping & Sourcing from China")
SOURCING_FEE = Decimal(os.environ.get("SOURCING_FEE", "50.00"))
CURRENCY = "usd"

# Stripe Checkout. Leave the keys empty to use demo payments while developing.
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

# When no Stripe key is configured, demo mode lets you click "confirm payment"
# to simulate a successful charge. Never enable this in production.
PAYMENTS_DEMO_MODE = env_bool("PAYMENTS_DEMO_MODE", DEBUG) and not STRIPE_SECRET_KEY

# OpenStreetMap (hotels, geocoding) and Wikimedia (photos) refuse requests that
# don't identify the app with a real contact e-mail. Set OSM_CONTACT_EMAIL in .env.
OSM_CONTACT_EMAIL = os.environ.get("OSM_CONTACT_EMAIL") or os.environ.get("IMAGE_FETCH_CONTACT", "")
SITE_URL = os.environ.get("SITE_URL", "")
OVERPASS_URLS = [
    u.strip() for u in os.environ.get(
        "OVERPASS_URLS",
        "https://overpass-api.de/api/interpreter,"
        "https://overpass.private.coffee/api/interpreter,"
        "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    ).split(",") if u.strip()
]

# --- Hotels & travel ---------------------------------------------------------
# Affiliate ids are appended to booking links so you earn commission.
TRIP_ALLIANCE_ID = os.environ.get("TRIP_ALLIANCE_ID", "")
TRIP_SID = os.environ.get("TRIP_SID", "")
BOOKING_AID = os.environ.get("BOOKING_AID", "")
HOTEL_SEARCH_RADIUS_M = int(os.environ.get("HOTEL_SEARCH_RADIUS_M", "2500"))
HOTELS_PER_MARKET = int(os.environ.get("HOTELS_PER_MARKET", "8"))

# --- Shipping estimator (USD). Indicative rates shown on /shipping/. ---------
SHIPPING_RATES = {
    "sea_lcl": {"label": "Sea · LCL", "per_cbm": 95, "minimum": 180, "days": "25–45"},
    "air": {"label": "Air cargo", "per_kg": 6.5, "minimum": 150, "days": "5–10"},
    "express": {"label": "Express courier", "per_kg": 11, "minimum": 45, "days": "3–7"},
}

# --- Live chat ---------------------------------------------------------------
# E-mail address that gets a notification when a customer sends a chat message.
SUPPORT_NOTIFY_EMAIL = os.environ.get("SUPPORT_NOTIFY_EMAIL", "")
# E-mail customers when staff reply (they also see it on the site).
SUPPORT_EMAIL_CUSTOMERS = env_bool("SUPPORT_EMAIL_CUSTOMERS", False)
# Outgoing e-mail. Without EMAIL_HOST, e-mails are printed to the console.
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER or "noreply@localhost")
EMAIL_BACKEND = (
    "django.core.mail.backends.smtp.EmailBackend" if EMAIL_HOST
    else "django.core.mail.backends.console.EmailBackend"
)
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
