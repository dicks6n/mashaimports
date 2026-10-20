from django.db.models import Sum

from .models import Conversation


def support(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {}
    if user.is_staff:
        unread = Conversation.objects.aggregate(t=Sum("staff_unread"))["t"] or 0
        return {"support_unread": unread}
    conv = Conversation.objects.filter(customer=user).only("customer_unread").first()
    return {"chat_unread": conv.customer_unread if conv else 0}
