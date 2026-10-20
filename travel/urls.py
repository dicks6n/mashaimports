from django.urls import path

from . import views

app_name = "travel"

urlpatterns = [
    path("hotels/", views.hotel_list, name="hotel_list"),
    path("trip-planner/", views.trip_planner, name="trip_planner"),
    path("trip-planner/<int:pk>/", views.trip_plan, name="trip_plan"),
    path("services/", views.service_list, name="service_list"),
    path("services/<slug:slug>/book/", views.service_book, name="service_book"),
    path("atlas/", views.atlas, name="atlas"),
]
