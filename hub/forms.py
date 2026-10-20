from django import forms

from catalog.models import Category, Market, Product
from sourcing.models import Plan, SourcingRequest
from travel.models import City, Hotel, Service, ServiceOrder

PHOTO = ["image", "image_url", "image_credit", "image_source", "image_query"]
TEXTAREA = forms.Textarea(attrs={"rows": 4})


class HubForm(forms.ModelForm):
    """ModelForm with checkbox lists for many-to-many fields."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field, forms.ModelMultipleChoiceField):
                field.widget = forms.CheckboxSelectMultiple(choices=field.choices)


class MarketForm(HubForm):
    class Meta:
        model = Market
        fields = ["name", "name_zh", "city", "province", "categories", "specialty", "summary", "description",
                  "established", "booths", "opening_hours", "featured", "order",
                  "address", "address_zh", "latitude", "longitude", "location_verified", "nearest_transit",
                  "insider_tips", *PHOTO]
        widgets = {"description": forms.Textarea(attrs={"rows": 6}), "insider_tips": TEXTAREA}


class ProductForm(HubForm):
    class Meta:
        model = Product
        fields = ["name", "category", "markets", "summary", "description", "price_from", "price_to", "moq",
                  "lead_time", "featured", *PHOTO]
        widgets = {"description": TEXTAREA}


class CategoryForm(HubForm):
    class Meta:
        model = Category
        fields = ["name", "tagline", "order", *PHOTO]


class HotelForm(HubForm):
    class Meta:
        model = Hotel
        fields = ["name", "name_zh", "city", "brand", "stars", "address", "latitude", "longitude",
                  "recommended", "note", "active", "website", "phone", "image", "image_url", "image_credit"]


class CityForm(HubForm):
    class Meta:
        model = City
        fields = ["name", "name_zh", "province", "latitude", "longitude", "trip_city_id"]


class ServiceForm(HubForm):
    class Meta:
        model = Service
        fields = ["name", "name_zh", "slug", "summary", "description", "price", "unit", "max_quantity", "order", "active"]
        widgets = {"description": TEXTAREA}


class PlanForm(HubForm):
    class Meta:
        model = Plan
        fields = ["name", "slug", "price", "duration_days", "tagline", "features", "highlighted", "order", "active"]
        widgets = {"features": forms.Textarea(attrs={"rows": 5})}


class OrderUpdateForm(forms.ModelForm):
    class Meta:
        model = SourcingRequest
        fields = ["status", "quoted_price", "shipping_quote", "tracking_number", "agent_notes"]
        widgets = {"agent_notes": forms.Textarea(attrs={"rows": 6, "placeholder": "Supplier options, photos sent, next steps… (the customer sees this)"})}


class ServiceOrderUpdateForm(forms.ModelForm):
    class Meta:
        model = ServiceOrder
        fields = ["status", "date", "end_date", "staff_notes"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "end_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "staff_notes": forms.Textarea(attrs={"rows": 5, "placeholder": "Interpreter name, pickup time, confirmation number… (the customer sees this)"}),
        }


class GrantPassForm(forms.Form):
    plan = forms.ModelChoiceField(queryset=Plan.objects.filter(active=True), empty_label=None)
    paid_offline = forms.BooleanField(
        required=False, label="Customer paid offline (record the payment)",
        help_text="Leave unticked to give the pass for free.",
    )
