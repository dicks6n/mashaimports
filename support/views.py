import logging
import os
from datetime import timedelta

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.db.models import F, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Conversation, Message

log = logging.getLogger(__name__)

MAX_BODY = 4000
MAX_FILE_MB = 8
ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".txt"}
RATE_LIMIT_PER_MINUTE = 20


# --- helpers -----------------------------------------------------------------

def _messages_after(conv, request):
    try:
        after = int(request.GET.get("after", 0))
    except ValueError:
        after = 0
    qs = conv.messages.select_related("sender").filter(id__gt=after)
    if not after:
        qs = qs.order_by("-id")[:60]  # first load: latest 60
        return [m.as_dict() for m in reversed(list(qs))]
    return [m.as_dict() for m in qs]


def _create_message(request, conv, from_staff):
    body = (request.POST.get("body") or "").strip()[:MAX_BODY]
    upload = request.FILES.get("attachment")
    if not body and not upload:
        return None, "Write a message or attach a file."
    if upload:
        if os.path.splitext(upload.name)[1].lower() not in ALLOWED_EXT:
            return None, "That file type isn't allowed. Send images, PDFs or office documents."
        if upload.size > MAX_FILE_MB * 1024 * 1024:
            return None, f"Files must be under {MAX_FILE_MB} MB."
    since = timezone.now() - timedelta(minutes=1)
    if conv.messages.filter(sender=request.user, created__gte=since).count() >= RATE_LIMIT_PER_MINUTE:
        return None, "You're sending messages too quickly. Please wait a moment."

    msg = Message.objects.create(
        conversation=conv, sender=request.user, from_staff=from_staff, body=body,
        attachment=upload or "", page=(request.POST.get("page") or "")[:300],
    )
    preview = body[:140] or f"📎 {os.path.basename(msg.attachment.name)}"
    updates = {"last_message_at": msg.created, "last_preview": preview}
    if from_staff:
        updates["customer_unread"] = F("customer_unread") + 1
    else:
        updates.update(staff_unread=F("staff_unread") + 1, closed=False)
    Conversation.objects.filter(pk=conv.pk).update(**updates)
    return msg, None


def _notify_staff(request, conv, msg):
    to = settings.SUPPORT_NOTIFY_EMAIL
    if not to:
        return
    link = request.build_absolute_uri(reverse("support:inbox_thread", args=[conv.pk]))
    try:
        send_mail(
            f"New chat message from {conv.customer_name}",
            f"{msg.body or '(attachment)'}\n\nReply: {link}",
            None, [to], fail_silently=True,
        )
    except Exception:  # never break the chat because e-mail is misconfigured
        log.exception("Could not send chat notification")


def _notify_customer(request, conv, msg):
    email = conv.customer.email
    if not (settings.SUPPORT_EMAIL_CUSTOMERS and email):
        return
    try:
        send_mail(
            f"{settings.SITE_NAME} replied to your message",
            f"{msg.body or '(attachment)'}\n\nOpen the chat: {request.build_absolute_uri(reverse('support:chat'))}",
            None, [email], fail_silently=True,
        )
    except Exception:
        log.exception("Could not send chat reply e-mail")


# --- customer side -----------------------------------------------------------

@login_required
def chat_page(request):
    return render(request, "support/chat_page.html")


@login_required
def customer_messages(request):
    conv = Conversation.objects.filter(customer=request.user).first()
    if not conv:
        return JsonResponse({"messages": [], "unread": 0})
    data = _messages_after(conv, request)
    if request.GET.get("seen") == "1" and conv.customer_unread:
        Conversation.objects.filter(pk=conv.pk).update(customer_unread=0)
        conv.customer_unread = 0
    return JsonResponse({"messages": data, "unread": conv.customer_unread})


@login_required
@require_POST
def customer_send(request):
    conv, created = Conversation.objects.get_or_create(customer=request.user)
    msg, error = _create_message(request, conv, from_staff=False)
    if error:
        return JsonResponse({"error": error}, status=400)
    _notify_staff(request, conv, msg)
    return JsonResponse({"message": msg.as_dict()})


# --- staff side ----------------------------------------------------------------

@staff_member_required
def inbox(request, pk=None):
    convs = Conversation.objects.select_related("customer", "assigned_to").exclude(last_message_at=None)
    show = request.GET.get("show", "open")
    q = request.GET.get("q", "").strip()
    if show == "open":
        convs = convs.filter(closed=False)
    elif show == "mine":
        convs = convs.filter(assigned_to=request.user)
    if q:
        convs = convs.filter(
            Q(customer__username__icontains=q) | Q(customer__first_name__icontains=q)
            | Q(customer__email__icontains=q) | Q(messages__body__icontains=q)
        ).distinct()
    active = get_object_or_404(Conversation.objects.select_related("customer"), pk=pk) if pk else None
    context = {"conversations": convs[:100], "active": active, "show": show, "q": q}
    if active:
        customer = active.customer
        context.update({
            "orders": customer.sourcing_requests.all()[:5],
            "services": customer.service_orders.select_related("service")[:5],
            "pass": customer.subscriptions.order_by("-expires_at").first(),
            "paid": customer.payments.filter(status="paid").aggregate(t=Sum("amount"))["t"] or 0,
        })
    return render(request, "support/inbox.html", context)


@staff_member_required
def staff_messages(request, pk):
    conv = get_object_or_404(Conversation, pk=pk)
    data = _messages_after(conv, request)
    if conv.staff_unread:
        Conversation.objects.filter(pk=pk).update(staff_unread=0)
    return JsonResponse({"messages": data})


@staff_member_required
@require_POST
def staff_send(request, pk):
    conv = get_object_or_404(Conversation, pk=pk)
    msg, error = _create_message(request, conv, from_staff=True)
    if error:
        return JsonResponse({"error": error}, status=400)
    if not conv.assigned_to_id:
        Conversation.objects.filter(pk=pk).update(assigned_to=request.user)
    _notify_customer(request, conv, msg)
    return JsonResponse({"message": msg.as_dict()})


@staff_member_required
@require_POST
def staff_toggle_closed(request, pk):
    conv = get_object_or_404(Conversation, pk=pk)
    conv.closed = not conv.closed
    conv.save(update_fields=["closed"])
    return JsonResponse({"closed": conv.closed})


@staff_member_required
def staff_poll(request):
    """Unread counts for the inbox list and the admin header badge."""
    convs = Conversation.objects.filter(staff_unread__gt=0).values("id", "staff_unread", "last_preview")
    return JsonResponse({
        "total": sum(c["staff_unread"] for c in convs),
        "conversations": {str(c["id"]): {"unread": c["staff_unread"], "preview": c["last_preview"]} for c in convs},
    })
