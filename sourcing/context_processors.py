from django.conf import settings

from .models import Subscription, has_location_access


def platform(request):
    return {
        "SITE_NAME": settings.SITE_NAME,
        "SITE_TAGLINE": settings.SITE_TAGLINE,
        "SOURCING_FEE": settings.SOURCING_FEE,
        "location_access": has_location_access(request.user),
        "current_pass": Subscription.current_for(request.user),
    }
