"""Payment provider glue.

With STRIPE_SECRET_KEY set, payments go through Stripe Checkout.
Without it (and PAYMENTS_DEMO_MODE on), a demo page simulates the charge.
"""

from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse


def stripe_enabled():
    return bool(settings.STRIPE_SECRET_KEY)


def _stripe():
    import stripe  # imported lazily so the dependency is optional in demo mode

    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


def start_checkout(request, payment):
    """Send the customer to pay for `payment`. Returns an HttpResponse."""
    if stripe_enabled():
        stripe = _stripe()
        session = stripe.checkout.Session.create(
            mode="payment",
            customer_email=request.user.email or None,
            client_reference_id=str(payment.pk),
            metadata={"payment_id": str(payment.pk)},
            line_items=[
                {
                    "quantity": 1,
                    "price_data": {
                        "currency": payment.currency,
                        "unit_amount": int(payment.amount * 100),
                        "product_data": {"name": f"{settings.SITE_NAME} · {payment.description}"},
                    },
                }
            ],
            success_url=request.build_absolute_uri(reverse("sourcing:checkout_success"))
            + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=request.build_absolute_uri(reverse("sourcing:checkout_cancel", args=[payment.pk])),
        )
        payment.provider = "stripe"
        payment.provider_ref = session.id
        payment.save(update_fields=["provider", "provider_ref"])
        return redirect(session.url, permanent=False)

    if settings.PAYMENTS_DEMO_MODE:
        payment.provider = "demo"
        payment.save(update_fields=["provider"])
        return redirect("sourcing:demo_checkout", pk=payment.pk)

    raise RuntimeError("No payment provider configured. Set STRIPE_SECRET_KEY.")


def session_is_paid(session_id):
    session = _stripe().checkout.Session.retrieve(session_id)
    return session.payment_status == "paid", session


def parse_webhook(payload, signature):
    return _stripe().Webhook.construct_event(payload, signature, settings.STRIPE_WEBHOOK_SECRET)
