from django.urls import path

from . import views

app_name = "catalog"

urlpatterns = [
    path("", views.home, name="home"),
    path("markets/", views.market_list, name="market_list"),
    path("markets/<slug:slug>/", views.market_detail, name="market_detail"),
    path("markets/<slug:slug>/save/", views.toggle_favorite, name="toggle_favorite"),
    path("products/", views.product_list, name="product_list"),
    path("products/<slug:slug>/", views.product_detail, name="product_detail"),
]
