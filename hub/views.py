import uuid
from datetime import timedelta
from decimal import Decimal
from functools import wraps

from django import forms as djforms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.core.files.storage import default_storage
from django.core.paginator import Paginator
from django.db.models import Count, Max, Q, Sum
from django.db.models.functions import TruncDate
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from catalog.models import Market
from ops import runner
from ops.models import JobRun
from sourcing.models import Payment, SourcingRequest, Subscription
from support.models import Conversation, Message
from travel.models import Hotel, MarketHotel, ServiceOrder, distance_km

from .forms import GrantPassForm, OrderUpdateForm, ServiceOrderUpdateForm
from .models import SiteSettings, whatsapp_link
from .resources import RESOURCES


def staff_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(), reverse("accounts:login"))
        if not request.user.is_staff:
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapped


# --- Dashboard ---------------------------------------------------------------

@staff_required
def dashboard(request):
    now = timezone.now()
    paid = Payment.objects.filter(status=Payment.Status.PAID)
    since30 = now - timedelta(days=30)

    # Revenue per day for the last 14 days (single series bar chart).
    start = timezone.localdate() - timedelta(days=13)  # site time zone, matching TruncDate below
    rows = (paid.filter(paid_at__date__gte=start).annotate(day=TruncDate("paid_at"))
            .values("day").annotate(total=Sum("amount")))
    by_day = {r["day"]: r["total"] for r in rows}
    days = [start + timedelta(days=i) for i in range(14)]
    values = [float(by_day.get(d, 0) or 0) for d in days]
    chart = _bar_chart(days, values)

    queued = SourcingRequest.objects.filter(status=SourcingRequest.Status.PAID).select_related("user")
    return render(request, "hub/dashboard.html", {
        "kpi": {
            "revenue30": paid.filter(paid_at__gte=since30).aggregate(t=Sum("amount"))["t"] or 0,
            "revenue_all": paid.aggregate(t=Sum("amount"))["t"] or 0,
            "orders_queued": queued.count(),
            "orders_active": SourcingRequest.objects.filter(status__in=["sourcing", "quoted", "shipping"]).count(),
            "services_open": ServiceOrder.objects.filter(status="confirmed").count(),
            "passes": Subscription.objects.filter(starts_at__lte=now, expires_at__gt=now).count(),
            "customers": User.objects.filter(is_staff=False).count(),
            "customers_new": User.objects.filter(is_staff=False, date_joined__gte=since30).count(),
            "chats_unread": Conversation.objects.aggregate(t=Sum("staff_unread"))["t"] or 0,
        },
        "chart": chart,
        "queued": queued[:6],
        "services": ServiceOrder.objects.filter(status="confirmed").select_related("user", "service", "city")[:6],
        "chats": Conversation.objects.exclude(last_message_at=None).select_related("customer")[:6],
        "signups": User.objects.filter(is_staff=False).order_by("-date_joined")[:6],
        "health": {
            "unverified": Market.objects.filter(location_verified=False).count(),
            "nophoto": Market.objects.filter(image="", image_url="").count(),
            "nohotels": Market.objects.filter(hotels=None).count(),
            "markets": Market.objects.count(),
        },
        "jobs": JobRun.objects.select_related("started_by")[:4],
        "site": SiteSettings.load(),
    })


def _bar_chart(days, values):
    """Geometry for a single-series column chart (SVG), computed server-side."""
    w, h, pad_l, pad_b, pad_t = 640, 200, 44, 26, 12
    plot_w, plot_h = w - pad_l - 8, h - pad_b - pad_t
    top = max(values) if any(values) else 0
    nice = _nice_ceiling(top) if top else 100
    slot = plot_w / len(values)
    bar_w = min(24, slot - 2)
    bars = []
    for i, (d, v) in enumerate(zip(days, values)):
        bh = (v / nice) * plot_h if nice else 0
        x = pad_l + i * slot + (slot - bar_w) / 2
        y = pad_t + plot_h - bh
        r = min(4, bh, bar_w / 2)
        base = pad_t + plot_h
        path = (f"M{x:.1f},{base:.1f} L{x:.1f},{y + r:.1f} Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f} "
                f"L{x + bar_w - r:.1f},{y:.1f} Q{x + bar_w:.1f},{y:.1f} {x + bar_w:.1f},{y + r:.1f} "
                f"L{x + bar_w:.1f},{base:.1f} Z") if bh > 0 else ""
        bars.append({
            "path": path, "label": f"{d:%b} {d.day}", "short": str(d.day), "value": v, "x": x, "cx": x + bar_w / 2,
            "hit_x": pad_l + i * slot, "hit_w": slot,
        })
    ticks = [{"y": pad_t + plot_h - (plot_h * k / 4), "label": _compact(nice * k / 4)} for k in range(5)]
    return {"w": w, "h": h, "bars": bars, "ticks": ticks, "pad_l": pad_l, "base": pad_t + plot_h,
            "plot_top": pad_t, "plot_h": plot_h, "total": sum(values), "label_y": h - 8}


def _nice_ceiling(v):
    for step in (10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000, 2500, 5000, 10000, 20000, 50000, 100000):
        if v <= step * 4:
            return step * 4
    return v * 1.1


def _compact(v):
    return f"${v / 1000:.1f}K".replace(".0K", "K") if v >= 1000 else f"${v:.0f}"


# --- Generic catalogue screens (add / edit / delete) --------------------------

def _resource(key):
    res = RESOURCES.get(key)
    if not res:
        raise Http404
    return res


@staff_required
def resource_list(request, key):
    res = _resource(key)
    qs = res.queryset()
    q = request.GET.get("q", "").strip()
    if q:
        cond = Q()
        for f in res.search:
            cond |= Q(**{f"{f}__icontains": q})
        qs = qs.filter(cond)
    active_filter = request.GET.get("f", "")
    if active_filter in res.filters:
        qs = qs.filter(res.filters[active_filter][1])
    qs = qs.distinct()
    page = Paginator(qs, 30).get_page(request.GET.get("page"))
    rows = [{"obj": o, "cells": [fn(o) for _, fn in res.columns]} for o in page.object_list]
    params = request.GET.copy()
    params.pop("page", None)
    return render(request, "hub/list.html", {
        "res": res, "rows": rows, "page": page, "q": q, "active_filter": active_filter,
        "headers": [label for label, _ in res.columns], "querystring": params.urlencode(),
    })


@staff_required
def resource_edit(request, key, pk=None):
    res = _resource(key)
    obj = get_object_or_404(res.model, pk=pk) if pk else None
    form = res.form_class(request.POST or None, request.FILES or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        if res.model is Hotel:
            _link_hotel_to_markets(obj)
        messages.success(request, f"{res.singular.capitalize()} “{obj}” saved.")
        if "save_add" in request.POST:
            return redirect("hub:resource_add", key=key)
        if "save_stay" in request.POST:
            return redirect("hub:resource_edit", key=key, pk=obj.pk)
        return redirect("hub:resource_list", key=key)

    fieldsets = [(title, [form[name] for name in names if name in form.fields]) for title, names in res.fieldsets]
    return render(request, "hub/form.html", {
        "res": res, "form": form, "obj": obj, "fieldsets": fieldsets,
        "jobs": JobRun.objects.filter(label__icontains=str(obj))[:3] if obj and res.key == "markets" else [],
    })


@staff_required
def resource_delete(request, key, pk):
    res = _resource(key)
    obj = get_object_or_404(res.model, pk=pk)
    if request.method == "POST":
        name = str(obj)
        try:
            obj.delete()
        except Exception as exc:  # e.g. a category still used by products (PROTECT)
            messages.error(request, f"Can't delete “{name}”: {exc.__class__.__name__}. It is still in use.")
            return redirect("hub:resource_edit", key=key, pk=pk)
        messages.success(request, f"Deleted “{name}”.")
        return redirect("hub:resource_list", key=key)
    return render(request, "hub/confirm_delete.html", {"res": res, "obj": obj})


def _link_hotel_to_markets(hotel):
    """Hand-added hotels: link to markets in the same city within 5 km."""
    for m in Market.objects.filter(city=hotel.city.name).exclude(latitude=None):
        d = distance_km(m.latitude, m.longitude, hotel.latitude, hotel.longitude)
        if d <= 5:
            MarketHotel.objects.update_or_create(market=m, hotel=hotel, defaults={"distance_km": Decimal(str(round(d, 2)))})


# --- Sourcing orders -----------------------------------------------------------

@staff_required
def order_list(request):
    qs = SourcingRequest.objects.select_related("user", "product", "market")
    status = request.GET.get("status", "")
    q = request.GET.get("q", "").strip()
    if status:
        qs = qs.filter(status=status)
    if q:
        qs = qs.filter(Q(reference__icontains=q) | Q(title__icontains=q) | Q(user__username__icontains=q)
                       | Q(user__email__icontains=q) | Q(destination__icontains=q))
    counts = dict(SourcingRequest.objects.values_list("status").annotate(n=Count("id")))
    tabs = [("", "All", sum(counts.values()))] + [(k, v, counts.get(k, 0)) for k, v in SourcingRequest.Status.choices]
    page = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(request, "hub/orders.html", {"page": page, "tabs": tabs, "status": status, "q": q})


@staff_required
def order_detail(request, reference):
    order = get_object_or_404(SourcingRequest.objects.select_related("user", "product", "market"), reference=reference)
    form = OrderUpdateForm(request.POST or None, instance=order)
    if request.method == "POST" and "update" in request.POST and form.is_valid():
        form.save()
        if request.POST.get("notify") == "on":
            _send_chat(request, order.user, f"Update on your order {order.reference} ({order.title}): "
                       f"{order.get_status_display()}." + (f"\n\n{order.agent_notes}" if order.agent_notes else ""))
        messages.success(request, f"Order {order.reference} updated.")
        return redirect("hub:order_detail", reference=reference)
    return render(request, "hub/order_detail.html", {
        "order": order, "form": form, "customer": order.user,
        "payments": order.payment_set.order_by("-created"),
        "whatsapp": _customer_whatsapp(order.user, f"Hello, about your order {order.reference}: "),
    })


@staff_required
@require_POST
def order_mark_paid(request, reference):
    order = get_object_or_404(SourcingRequest, reference=reference)
    if not order.is_paid:
        p = Payment.objects.create(user=order.user, kind=Payment.Kind.SOURCING, amount=order.fee,
                                   currency=settings.CURRENCY, sourcing_request=order, provider="manual")
        p.mark_paid()
        messages.success(request, f"Recorded an offline payment of ${order.fee} for {order.reference}.")
    return redirect("hub:order_detail", reference=reference)


# --- Service bookings ----------------------------------------------------------

@staff_required
def service_order_list(request):
    qs = ServiceOrder.objects.select_related("user", "service", "city")
    status = request.GET.get("status", "")
    if status:
        qs = qs.filter(status=status)
    counts = dict(ServiceOrder.objects.values_list("status").annotate(n=Count("id")))
    tabs = [("", "All", sum(counts.values()))] + [(k, v, counts.get(k, 0)) for k, v in ServiceOrder.Status.choices]
    page = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(request, "hub/service_orders.html", {"page": page, "tabs": tabs, "status": status})


@staff_required
def service_order_detail(request, pk):
    order = get_object_or_404(ServiceOrder.objects.select_related("user", "service", "city", "market", "hotel"), pk=pk)
    form = ServiceOrderUpdateForm(request.POST or None, instance=order)
    if request.method == "POST" and "update" in request.POST and form.is_valid():
        form.save()
        if request.POST.get("notify") == "on":
            _send_chat(request, order.user, f"Update on your {order.service.name} booking: {order.get_status_display()}."
                       + (f"\n\n{order.staff_notes}" if order.staff_notes else ""))
        messages.success(request, "Booking updated.")
        return redirect("hub:service_order_detail", pk=pk)
    return render(request, "hub/service_order_detail.html", {
        "order": order, "form": form, "customer": order.user,
        "whatsapp": whatsapp_link(order.phone, f"Hello, about your {order.service.name} booking: "),
    })


@staff_required
@require_POST
def service_order_mark_paid(request, pk):
    order = get_object_or_404(ServiceOrder, pk=pk)
    if not order.paid_at:
        p = Payment.objects.create(user=order.user, kind=Payment.Kind.SERVICE, amount=order.amount,
                                   currency=settings.CURRENCY, service_order=order, provider="manual")
        p.mark_paid()
        messages.success(request, f"Recorded an offline payment of ${order.amount}.")
    return redirect("hub:service_order_detail", pk=pk)


# --- Customers -------------------------------------------------------------------

@staff_required
def customer_list(request):
    qs = (User.objects.filter(is_staff=False)
          .annotate(orders=Count("sourcing_requests", distinct=True),
                    paid=Sum("payments__amount", filter=Q(payments__status="paid")),
                    last_paid=Max("payments__paid_at"))
          .order_by("-date_joined"))
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(username__icontains=q) | Q(email__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q))
    page = Paginator(qs, 30).get_page(request.GET.get("page"))
    now = timezone.now()
    active_pass = set(Subscription.objects.filter(starts_at__lte=now, expires_at__gt=now).values_list("user_id", flat=True))
    return render(request, "hub/customers.html", {"page": page, "q": q, "active_pass": active_pass})


@staff_required
def customer_detail(request, pk):
    customer = get_object_or_404(User, pk=pk)
    grant = GrantPassForm(request.POST or None)
    if request.method == "POST" and "grant" in request.POST and grant.is_valid():
        plan = grant.cleaned_data["plan"]
        if grant.cleaned_data["paid_offline"]:
            Payment.objects.create(user=customer, kind=Payment.Kind.SUBSCRIPTION, amount=plan.price,
                                   currency=settings.CURRENCY, plan=plan, provider="manual").mark_paid()
        else:
            current = Subscription.current_for(customer)
            start = current.expires_at if current else timezone.now()
            Subscription.objects.create(user=customer, plan=plan, starts_at=start,
                                        expires_at=start + timedelta(days=plan.duration_days))
        messages.success(request, f"{plan.name} given to {customer.get_full_name() or customer.username}.")
        return redirect("hub:customer_detail", pk=pk)

    conv = Conversation.objects.filter(customer=customer).first()
    phones = list(customer.service_orders.exclude(phone="").values_list("phone", flat=True)[:1])
    return render(request, "hub/customer_detail.html", {
        "customer": customer, "grant": grant, "conv": conv,
        "recent_messages": conv.messages.select_related("sender").order_by("-id")[:6][::-1] if conv else [],
        "orders": customer.sourcing_requests.all()[:10],
        "services": customer.service_orders.select_related("service")[:10],
        "passes": customer.subscriptions.select_related("plan")[:10],
        "payments": customer.payments.order_by("-created")[:10],
        "trips": customer.trip_plans.select_related("city")[:5],
        "favorites": customer.favorites.select_related("market")[:8],
        "paid": customer.payments.filter(status="paid").aggregate(t=Sum("amount"))["t"] or 0,
        "now": timezone.now(),
        "whatsapp": whatsapp_link(phones[0] if phones else "", "Hello from Masha Imports! "),
        "phone": phones[0] if phones else "",
    })


# --- Messaging ------------------------------------------------------------------

def _send_chat(request, customer, body, attachment=None):
    conv, _ = Conversation.objects.get_or_create(customer=customer)
    msg = Message.objects.create(conversation=conv, sender=request.user, from_staff=True, body=body,
                                 attachment=attachment or "")
    preview = body[:140] or "📎 attachment"
    Conversation.objects.filter(pk=conv.pk).update(
        last_message_at=msg.created, last_preview=preview, customer_unread=conv.customer_unread + 1,
        assigned_to=conv.assigned_to or request.user,
    )
    return conv


@staff_required
@require_POST
def send_message(request, pk):
    """Send a chat message to a customer from any hub page."""
    customer = get_object_or_404(User, pk=pk)
    body = (request.POST.get("body") or "").strip()
    upload = request.FILES.get("attachment")
    if not body and not upload:
        messages.error(request, "Write a message first.")
    else:
        _send_chat(request, customer, body[:4000], upload)
        messages.success(request, f"Message sent to {customer.get_full_name() or customer.username}. They'll see it in their chat.")
    nxt = request.POST.get("next") or reverse("hub:customer_detail", args=[pk])
    return redirect(nxt if nxt.startswith("/") else reverse("hub:customer_detail", args=[pk]))


def _customer_whatsapp(user, text):
    phone = user.service_orders.exclude(phone="").values_list("phone", flat=True).first()
    return whatsapp_link(phone, text) if phone else ""


# --- Payments --------------------------------------------------------------------

@staff_required
def payment_list(request):
    qs = Payment.objects.select_related("user", "plan", "sourcing_request", "service_order__service")
    kind, status = request.GET.get("kind", ""), request.GET.get("status", "paid")
    if kind:
        qs = qs.filter(kind=kind)
    if status:
        qs = qs.filter(status=status)
    totals = qs.aggregate(t=Sum("amount"), n=Count("id"))
    page = Paginator(qs, 40).get_page(request.GET.get("page"))
    return render(request, "hub/payments.html", {
        "page": page, "kind": kind, "status": status, "totals": totals,
        "kinds": Payment.Kind.choices, "statuses": Payment.Status.choices,
    })


# --- Tools -----------------------------------------------------------------------

@staff_required
def tools(request):
    runner.mark_stale_runs()
    return render(request, "hub/tools.html", {
        "runs": JobRun.objects.select_related("started_by")[:15],
        "contact_ok": _contact_ok(),
        "health": {
            "markets": Market.objects.count(),
            "unverified": Market.objects.filter(location_verified=False).count(),
            "nophoto": Market.objects.filter(image="", image_url="").count(),
            "nohotels": Market.objects.filter(hotels=None).count(),
        },
    })


def _contact_ok():
    email = (settings.OSM_CONTACT_EMAIL or "").strip()
    return email.count("@") == 1 and " " not in email and "example." not in email and "yourdomain" not in email


def _start(request, command, label=None, args=None, options=None):
    if runner.already_running(command):
        messages.warning(request, f"“{runner.TOOLS[command]}” is already running. Wait for it to finish.")
        return redirect("hub:tools")
    job = runner.start(command, user=request.user, label=label, args=args, options=options)
    return redirect("hub:job", pk=job.pk)


@staff_required
@require_POST
def tool_run(request):
    p, tool = request.POST, request.POST.get("tool")
    if tool == "geocode_markets":
        opts = {"dry_run": p.get("dry_run") == "on"}
        if p.get("market"):
            opts["market"] = p["market"]
        return _start(request, tool, options=opts)
    if tool == "sync_hotels":
        opts = {}
        if p.get("market"):
            opts["market"] = p["market"]
        if p.get("radius", "").isdigit():
            opts["radius"] = int(p["radius"])
        return _start(request, tool, options=opts)
    if tool == "fetch_images":
        opts = {"force": p.get("force") == "on"}
        if p.get("only") in {"markets", "products", "categories"}:
            opts["only"] = p["only"]
        return _start(request, tool, options=opts)
    if tool == "import_markets":
        upload = request.FILES.get("csv_file")
        if not upload or not upload.name.lower().endswith(".csv"):
            messages.error(request, "Choose a .csv file to import.")
            return redirect("hub:tools")
        name = default_storage.save(f"imports/{uuid.uuid4().hex}.csv", upload)
        return _start(request, tool, label=f"Import markets from {upload.name}", args=[default_storage.path(name)])
    messages.error(request, "Unknown tool.")
    return redirect("hub:tools")


@staff_required
@require_POST
def market_tool(request, pk):
    """Run a tool for one market from its edit page."""
    market = get_object_or_404(Market, pk=pk)
    tool = request.POST.get("tool")
    labels = {"sync_hotels": "Find hotels", "geocode_markets": "Refine location", "fetch_images": "Fetch photo"}
    if tool not in labels:
        raise Http404
    opts = {"ids": str(market.pk)}
    if tool == "fetch_images":
        opts.update(only="markets", force=True)
    return _start(request, tool, label=f"{labels[tool]} · {market}", options=opts)


@staff_required
def job(request, pk):
    return render(request, "hub/job.html", {"job": get_object_or_404(JobRun, pk=pk)})


@staff_required
def job_log(request, pk):
    j = get_object_or_404(JobRun, pk=pk)
    return JsonResponse({"status": j.status, "label": j.get_status_display(), "log": j.log})


# --- Settings ----------------------------------------------------------------------

class SiteSettingsForm(djforms.ModelForm):
    class Meta:
        model = SiteSettings
        fields = ["whatsapp_number", "whatsapp_message", "show_whatsapp", "chat_enabled", "chat_greeting",
                  "reply_time", "support_email"]


@staff_required
def site_settings(request):
    obj = SiteSettings.load()
    form = SiteSettingsForm(request.POST or None, instance=SiteSettings.objects.get(pk=obj.pk))
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Settings saved. The chat pop-up updates straight away.")
        return redirect("hub:settings")
    return render(request, "hub/settings.html", {"form": form, "site": obj})
