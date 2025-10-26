# -------------------------------------------------------------------
# TIERED FINISHING PRICE ADMIN (cleaned and working)
# -------------------------------------------------------------------
from django import forms
from django.contrib import admin
from .models import TieredFinishingPrice


class TieredFinishingPriceAdminForm(forms.ModelForm):
    test_quantity = forms.IntegerField(
        required=False,
        label="Test Quantity",
        help_text="Enter a quantity to preview total cost (not saved)."
    )
    estimated_total = forms.CharField(
        required=False,
        label="Estimated Total",
        disabled=True
    )

    class Meta:
        model = TieredFinishingPrice
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()
        qty = cleaned_data.get("test_quantity")
        price = cleaned_data.get("price")
        if qty and price:
            try:
                total = qty * price
                cleaned_data["estimated_total"] = f"{total:.2f}"
            except Exception:
                cleaned_data["estimated_total"] = "—"
        return cleaned_data


@admin.register(TieredFinishingPrice)
class TieredFinishingPriceAdmin(admin.ModelAdmin):
    form = TieredFinishingPriceAdminForm

    readonly_fields = ("id",)
    list_display = ("machine", "min_quantity", "max_quantity", "company")
    list_filter = ("machine", "company")
    search_fields = ("machine__name", "company__name")
    autocomplete_fields = ("machine", "company")
    ordering = ("machine", "min_quantity")

    fieldsets = (
        (None, {
            "fields": (
                ("machine", "company"),
                ("min_quantity", "max_quantity", "price"),
                ("test_quantity", "estimated_total"),
            )
        }),
    )
