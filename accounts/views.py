from django import forms
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.db.models import Sum
from django.shortcuts import redirect, render


class SignupForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(label="Full name", max_length=150)

    class Meta:
        model = User
        fields = ["first_name", "username", "email"]


def signup(request):
    if request.user.is_authenticated:
        return redirect("accounts:dashboard")
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect(request.GET.get("next") or "accounts:dashboard")
    return render(request, "accounts/signup.html", {"form": form})


@login_required
def dashboard(request):
    if request.user.is_staff:
        return redirect("hub:dashboard")
    return render(
        request,
        "accounts/dashboard.html",
        {
            "requests": request.user.sourcing_requests.select_related("product", "market"),
            "passes": request.user.subscriptions.select_related("plan")[:5],
            "service_orders": request.user.service_orders.select_related("service", "city"),
            "trip_plans": request.user.trip_plans.select_related("city")[:6],
            "favorites": request.user.favorites.select_related("market")[:12],
            "total_paid": request.user.payments.filter(status="paid").aggregate(t=Sum("amount"))["t"] or 0,
        },
    )
