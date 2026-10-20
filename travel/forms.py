from datetime import date, timedelta

from django import forms

from catalog.models import Market

from .models import City, ServiceOrder


class TripPlanForm(forms.Form):
    city = forms.ModelChoiceField(queryset=City.objects.all(), empty_label="Choose a city")
    markets = forms.ModelMultipleChoiceField(
        queryset=Market.objects.all(), widget=forms.CheckboxSelectMultiple, required=False,
        help_text="Leave empty and we'll pick the best markets in the city for you.",
    )
    arrival = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    nights = forms.IntegerField(min_value=1, max_value=30, initial=3)
    guests = forms.IntegerField(min_value=1, max_value=8, initial=1)

    def clean_arrival(self):
        arrival = self.cleaned_data["arrival"]
        if arrival < date.today():
            raise forms.ValidationError("Arrival date can't be in the past.")
        return arrival

    def clean(self):
        data = super().clean()
        city, markets = data.get("city"), data.get("markets")
        if city and markets:
            data["markets"] = [m for m in markets if m.city == city.name]
        return data


class ServiceOrderForm(forms.ModelForm):
    class Meta:
        model = ServiceOrder
        fields = ["quantity", "city", "market", "date", "end_date", "guests", "phone", "details"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "details": forms.Textarea(attrs={"rows": 4, "placeholder": "Anything we should know: products, budget, flight number, hotel preferences…"}),
            "phone": forms.TextInput(attrs={"placeholder": "+234 …"}),
        }
        labels = {"end_date": "until (optional)", "quantity": "quantity"}

    def __init__(self, *args, service=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.service = service
        self.fields["quantity"].widget = forms.NumberInput(attrs={"min": 1, "max": service.max_quantity})
        self.fields["quantity"].label = f"how many ({service.unit.replace('per ', '')}s)"
        if service.max_quantity == 1:
            self.fields["quantity"].widget = forms.HiddenInput()
        self.fields["city"].empty_label = "Choose a city"
        self.fields["market"].required = False
        self.fields["market"].queryset = Market.objects.order_by("city", "name")
        self.fields["date"].required = True

    def clean_quantity(self):
        q = self.cleaned_data["quantity"] or 1
        if not 1 <= q <= self.service.max_quantity:
            raise forms.ValidationError(f"Choose between 1 and {self.service.max_quantity}.")
        return q

    def clean(self):
        data = super().clean()
        start, end = data.get("date"), data.get("end_date")
        if start and start < date.today():
            self.add_error("date", "Date can't be in the past.")
        if start and end and end < start:
            self.add_error("end_date", "End date must be after the start date.")
        return data


def parse_stay(params):
    """Read checkin/checkout/guests from GET params, with sensible defaults."""
    from .booking import default_dates

    checkin, checkout = default_dates()
    try:
        checkin = date.fromisoformat(params.get("checkin", "")) or checkin
    except ValueError:
        pass
    try:
        checkout = date.fromisoformat(params.get("checkout", ""))
    except ValueError:
        checkout = checkin + timedelta(days=3)
    if checkout <= checkin:
        checkout = checkin + timedelta(days=1)
    try:
        guests = max(1, min(8, int(params.get("guests", 1))))
    except ValueError:
        guests = 1
    return checkin, checkout, guests
