from django.contrib import admin
from .models import Machine
from pricing.models import (
    DigitalPrintPrice,
    LargeFormatPrintPrice,
    OffsetPlatePrice,
    OffsetRunPrice,
    ScreenSetupPrice,
    ScreenRunPrice,
    UVDTFPrintPrice,
    TieredFinishingPrice,
)

# -------------------------------------------------------------------
# INLINE BASE — Common Style
# -------------------------------------------------------------------
class BasePricingInline(admin.TabularInline):
    extra = 1
    show_change_link = False
    readonly_fields = ("id",)
    can_delete = True
    verbose_name_plural = "Pricing"
    ordering = ("id",)


# -------------------------------------------------------------------
# DIGITAL PRINT INLINE
# -------------------------------------------------------------------
class DigitalPrintPriceInline(BasePricingInline):
    model = DigitalPrintPrice
    fields = (
        "company",
        "machine",
        "paper_type",
        "single_side_price",
        "double_side_price",
        "currency",
        "size",
    )
    autocomplete_fields = ("paper_type", "size",)
    verbose_name = "Digital Print Price"



# -------------------------------------------------------------------
# LARGE FORMAT INLINE
# -------------------------------------------------------------------
class LargeFormatPrintPriceInline(BasePricingInline):
    model = LargeFormatPrintPrice
    fields = (
        "material",
        "roll_width_m",
        "price_per_sq_meter",
        "currency",
    )
    autocomplete_fields = ("material",)
    verbose_name = "Large Format Price"


# -------------------------------------------------------------------
# TIERED FINISHING INLINE
# -------------------------------------------------------------------
class TieredFinishingPriceInline(BasePricingInline):
    model = TieredFinishingPrice
    fk_name = "machine"  # Important: use correct FK
    fields = (
        "machine",
        "service",
        "min_quantity",
        "max_quantity",
        "unit_price",
        "setup_fee",
    )
    autocomplete_fields = ("machine", "service",)
    verbose_name = "Finishing Tier"

    def get_queryset(self, request):
        """Show only tiers linked to this machine."""
        qs = super().get_queryset(request)
        return qs.select_related("machine", "service")


# -------------------------------------------------------------------
# OFFSET RUN INLINE
# -------------------------------------------------------------------
class OffsetRunPriceInline(BasePricingInline):
    model = OffsetRunPrice
    fields = (
        "paper_type",
        "price_per_sheet_per_color",
        "currency",
    )
    autocomplete_fields = ("paper_type",)
    verbose_name = "Offset Run Price"


# -------------------------------------------------------------------
# UV DTF INLINE
# -------------------------------------------------------------------
class UVDTFPrintPriceInline(BasePricingInline):
    model = UVDTFPrintPrice
    fields = ("material", "price_per_sq_meter", "currency")
    autocomplete_fields = ("material",)
    verbose_name = "UV DTF Price"


# -------------------------------------------------------------------
# MACHINE ADMIN
# -------------------------------------------------------------------
@admin.register(Machine)
class MachineAdmin(admin.ModelAdmin):
    """
    Admin for Machine model with pricing inlines for:
    - Digital printing
    - Finishing (tiered)
    - Large format
    - UV DTF
    - Offset
    etc.
    """

    list_display = ("name", "company", "machine_type")
    list_filter = ("company", "machine_type")
    search_fields = ("name", "company__name")
    ordering = ("company", "name")
    autocomplete_fields = ("company",)
    filter_horizontal = ("supported_sizes",)
    readonly_fields = ("slug",)

    inlines = [
        DigitalPrintPriceInline,
        LargeFormatPrintPriceInline,
        TieredFinishingPriceInline,
        OffsetRunPriceInline,
        UVDTFPrintPriceInline,
    ]

    fieldsets = (
        ("Core Info", {
            "fields": ("company", "name", "machine_type", "slug"),
        }),
        ("Size Capabilities", {
            "fields": ("supported_sizes", "supports_client_custom_size"),
        }),
        ("Additional Details", {
            "fields": ("description",),
        }),
    )
