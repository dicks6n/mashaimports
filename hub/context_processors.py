from django.db.models import Sum

from sourcing.models import SourcingRequest
from support.models import Conversation
from travel.models import ServiceOrder

from .models import SiteSettings


def site_settings(request):
    """Business settings for every page; badge counts for staff pages."""
    try:
        settings_obj = SiteSettings.load()
    except Exception:  # table not created yet (before migrate)
        settings_obj = None
    ctx = {"site_settings": settings_obj}
    user = getattr(request, "user", None)
    if user and user.is_authenticated and user.is_staff and request.path.startswith(("/hub", "/inbox")):
        ctx["hub_counts"] = {
            "orders": SourcingRequest.objects.filter(status=SourcingRequest.Status.PAID).count(),
            "services": ServiceOrder.objects.filter(status=ServiceOrder.Status.CONFIRMED).count(),
            "chats": Conversation.objects.aggregate(t=Sum("staff_unread"))["t"] or 0,
        }
    return ctx
