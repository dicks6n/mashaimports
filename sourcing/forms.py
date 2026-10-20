from django import forms

from .models import SourcingRequest


class SourcingRequestForm(forms.ModelForm):
    class Meta:
        model = SourcingRequest
        fields = [
            "title",
            "details",
            "quantity",
            "target_price",
            "destination",
            "shipping_method",
            "reference_image",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "e.g. Stainless steel insulated bottles, 750ml"}),
            "details": forms.Textarea(
                attrs={"rows": 5, "placeholder": "Materials, sizes, colours, logo printing, packaging, certifications…"}
            ),
            "quantity": forms.TextInput(attrs={"placeholder": "e.g. 500 pcs"}),
            "target_price": forms.TextInput(attrs={"placeholder": "e.g. $2.40 / pc (optional)"}),
            "destination": forms.TextInput(attrs={"placeholder": "e.g. Lagos, Nigeria"}),
        }
