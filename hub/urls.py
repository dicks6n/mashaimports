from django.urls import path

from . import views

app_name = "hub"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("orders/", views.order_list, name="orders"),
    path("orders/<str:reference>/", views.order_detail, name="order_detail"),
    path("orders/<str:reference>/mark-paid/", views.order_mark_paid, name="order_mark_paid"),
    path("bookings/", views.service_order_list, name="service_orders"),
    path("bookings/<int:pk>/", views.service_order_detail, name="service_order_detail"),
    path("bookings/<int:pk>/mark-paid/", views.service_order_mark_paid, name="service_order_mark_paid"),
    path("customers/", views.customer_list, name="customers"),
    path("customers/<int:pk>/", views.customer_detail, name="customer_detail"),
    path("customers/<int:pk>/message/", views.send_message, name="send_message"),
    path("payments/", views.payment_list, name="payments"),
    path("tools/", views.tools, name="tools"),
    path("tools/run/", views.tool_run, name="tool_run"),
    path("tools/market/<int:pk>/", views.market_tool, name="market_tool"),
    path("tools/jobs/<int:pk>/", views.job, name="job"),
    path("tools/jobs/<int:pk>/log/", views.job_log, name="job_log"),
    path("settings/", views.site_settings, name="settings"),
    path("<slug:key>/", views.resource_list, name="resource_list"),
    path("<slug:key>/new/", views.resource_edit, name="resource_add"),
    path("<slug:key>/<int:pk>/", views.resource_edit, name="resource_edit"),
    path("<slug:key>/<int:pk>/delete/", views.resource_delete, name="resource_delete"),
]
