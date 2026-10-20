from django.urls import path

from . import views

app_name = "sourcing"

urlpatterns = [
    path("pricing/", views.pricing, name="pricing"),
    path("shipping/", views.shipping, name="shipping"),
    path("source/new/", views.new_request, name="new_request"),
    path("source/<str:reference>/", views.request_detail, name="request_detail"),
    path("source/<str:reference>/pay/", views.pay_request, name="pay_request"),
    path("pass/<slug:slug>/buy/", views.buy_plan, name="buy_plan"),
    path("checkout/demo/<int:pk>/", views.demo_checkout, name="demo_checkout"),
    path("checkout/success/", views.checkout_success, name="checkout_success"),
    path("checkout/cancel/<int:pk>/", views.checkout_cancel, name="checkout_cancel"),
    path("webhooks/stripe/", views.stripe_webhook, name="stripe_webhook"),
]
