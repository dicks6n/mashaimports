import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from catalog.models import Market, Product

from . import payments
from .forms import SourcingRequestForm
from .models import Payment, Plan, SourcingRequest

log = logging.getLogger(__name__)


def pricing(request):
    return render(request, "sourcing/pricing.html", {"plans": Plan.objects.filter(active=True)})


def shipping(request):
    return render(request, "sourcing/shipping.html", {"rates": settings.SHIPPING_RATES})


@login_required
def new_request(request):
    product = Product.objects.filter(slug=request.GET.get("product")).first()
    market = Market.objects.filter(slug=request.GET.get("market")).first()

    if request.method == "POST":
        form = SourcingRequestForm(request.POST, request.FILES)
        if form.is_valid():
            req = form.save(commit=False)
            req.user = request.user
            req.product = Product.objects.filter(pk=request.POST.get("product_id") or None).first()
            req.market = Market.objects.filter(pk=request.POST.get("market_id") or None).first()
            req.fee = settings.SOURCING_FEE
            req.save()
            payment = Payment.objects.create(
                user=request.user,
                kind=Payment.Kind.SOURCING,
                amount=req.fee,
                currency=settings.CURRENCY,
                sourcing_request=req,
            )
            return payments.start_checkout(request, payment)
    else:
        initial = {}
        if product:
            initial["title"] = product.name
            initial["quantity"] = product.moq
        form = SourcingRequestForm(initial=initial)

    return render(request, "sourcing/request_form.html", {"form": form, "product": product, "market": market})


@login_required
def request_detail(request, reference):
    req = get_object_or_404(SourcingRequest, reference=reference, user=request.user)
    steps = ["Paid", "Sourcing", "Quoted", "Shipped", "Delivered"]
    return render(request, "sourcing/request_detail.html", {"req": req, "steps": steps})


@login_required
def pay_request(request, reference):
    req = get_object_or_404(SourcingRequest, reference=reference, user=request.user)
    if req.is_paid:
        return redirect(req)
    payment = Payment.objects.create(
        user=request.user, kind=Payment.Kind.SOURCING, amount=req.fee, currency=settings.CURRENCY, sourcing_request=req
    )
    return payments.start_checkout(request, payment)


@login_required
@require_POST
def buy_plan(request, slug):
    plan = get_object_or_404(Plan, slug=slug, active=True)
    payment = Payment.objects.create(
        user=request.user, kind=Payment.Kind.SUBSCRIPTION, amount=plan.price, currency=settings.CURRENCY, plan=plan
    )
    return payments.start_checkout(request, payment)


@login_required
def demo_checkout(request, pk):
    if not settings.PAYMENTS_DEMO_MODE:
        raise Http404
    payment = get_object_or_404(Payment, pk=pk, user=request.user)
    if request.method == "POST":
        payment.mark_paid()
        return _after_payment(request, payment)
    return render(request, "sourcing/demo_checkout.html", {"payment": payment})


@login_required
def checkout_success(request):
    session_id = request.GET.get("session_id", "")
    payment = get_object_or_404(Payment, provider_ref=session_id, user=request.user)
    paid, _ = payments.session_is_paid(session_id)
    if paid:
        payment.mark_paid()
    return _after_payment(request, payment)


@login_required
def checkout_cancel(request, pk):
    payment = get_object_or_404(Payment, pk=pk, user=request.user)
    messages.warning(request, "Payment was cancelled — nothing was charged.")
    if payment.sourcing_request:
        return redirect(payment.sourcing_request)
    if payment.service_order:
        return redirect("travel:service_list")
    return redirect("sourcing:pricing")


def _after_payment(request, payment):
    if payment.status != Payment.Status.PAID:
        messages.info(request, "We're still confirming your payment. This page will update shortly.")
    elif payment.kind == Payment.Kind.SOURCING:
        messages.success(request, "Payment received — a sourcing agent has your request and is heading to market.")
        return redirect(payment.sourcing_request)
    elif payment.kind == Payment.Kind.SERVICE:
        messages.success(request, f"{payment.service_order.service.name} confirmed — our team will contact you on WhatsApp within 24 hours.")
    else:
        messages.success(request, "Your location pass is active. Every market address and map is now unlocked.")
    return redirect("accounts:dashboard")


@csrf_exempt
@require_POST
def stripe_webhook(request):
    if not payments.stripe_enabled():
        raise Http404
    try:
        event = payments.parse_webhook(request.body, request.headers.get("Stripe-Signature", ""))
    except Exception:  # bad payload or signature
        return HttpResponseBadRequest()
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        payment = Payment.objects.filter(provider_ref=session["id"]).first()
        if payment and session.get("payment_status") == "paid":
            payment.mark_paid()
        elif not payment:
            log.warning("Stripe session %s has no matching payment", session["id"])
    return HttpResponse(status=200)
