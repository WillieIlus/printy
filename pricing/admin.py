from django.contrib import admin
from .models import (
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
# BASE ADMIN CLASS
# -------------------------------------------------------------------
class BasePricingAdmin(admin.ModelAdmin):
    """
    Base admin for pricing models.
    Provides common fields like `id` as readonly and ordering by company.
    """
    readonly_fields = ("id",)
    ordering = ("company",)
    list_per_page = 25
    search_help_text = "Search by machine, company or material name"


# -------------------------------------------------------------------
# DIGITAL PRINT PRICE ADMIN
# -------------------------------------------------------------------
@admin.register(DigitalPrintPrice)
class DigitalPrintPriceAdmin(BasePricingAdmin):
    list_display = (
        "machine",
        "paper_type",
        "single_side_price",
        "double_side_price",
        "currency",
        "company",
    )
    list_filter = ("company", "machine")
    search_fields = ("machine__name", "company__name", "paper_type__name")
    autocomplete_fields = ("company", "machine", "paper_type")


# -------------------------------------------------------------------
# LARGE FORMAT PRINT PRICE ADMIN
# -------------------------------------------------------------------
@admin.register(LargeFormatPrintPrice)
class LargeFormatPrintPriceAdmin(BasePricingAdmin):
    list_display = (
        "machine",
        "material",
        "roll_width_m",
        "price_per_sq_meter",
        "currency",
        "company",
    )
    list_filter = ("company", "machine", "material")
    search_fields = ("machine__name", "company__name", "material__name")
    autocomplete_fields = ("company", "machine", "material")


# -------------------------------------------------------------------
# OFFSET PLATE PRICE ADMIN
# -------------------------------------------------------------------
@admin.register(OffsetPlatePrice)
class OffsetPlatePriceAdmin(BasePricingAdmin):
    list_display = ("name", "setup_cost", "company")
    list_filter = ("company",)
    search_fields = ("name", "company__name")
    autocomplete_fields = ("company",)


# -------------------------------------------------------------------
# OFFSET RUN PRICE ADMIN
# -------------------------------------------------------------------
@admin.register(OffsetRunPrice)
class OffsetRunPriceAdmin(BasePricingAdmin):
    list_display = (
        "machine",
        "paper_type",
        "price_per_sheet_per_color",
        "currency",
        "company",
    )
    list_filter = ("company", "machine")
    search_fields = ("machine__name", "paper_type__name", "company__name")
    autocomplete_fields = ("company", "machine", "paper_type")


# -------------------------------------------------------------------
# SCREEN SETUP PRICE ADMIN
# -------------------------------------------------------------------
@admin.register(ScreenSetupPrice)
class ScreenSetupPriceAdmin(BasePricingAdmin):
    list_display = ("name", "setup_cost", "company")
    list_filter = ("company",)
    search_fields = ("name", "company__name")
    autocomplete_fields = ("company",)


# -------------------------------------------------------------------
# SCREEN RUN PRICE ADMIN
# -------------------------------------------------------------------
@admin.register(ScreenRunPrice)
class ScreenRunPriceAdmin(BasePricingAdmin):
    list_display = ("machine", "run_cost_per_item_per_color", "currency", "company")
    list_filter = ("company", "machine")
    search_fields = ("machine__name", "company__name")
    autocomplete_fields = ("company", "machine")


# -------------------------------------------------------------------
# UV DTF PRINT PRICE ADMIN
# -------------------------------------------------------------------
@admin.register(UVDTFPrintPrice)
class UVDTFPrintPriceAdmin(BasePricingAdmin):
    list_display = ("machine", "material", "price_per_sq_meter", "currency", "company")
    list_filter = ("company", "machine", "material")
    search_fields = ("machine__name", "company__name", "material__name")
    autocomplete_fields = ("company", "machine", "material")


# -------------------------------------------------------------------
# TIERED FINISHING PRICE ADMIN
# -------------------------------------------------------------------
@admin.register(TieredFinishingPrice)
class TieredFinishingPriceAdmin(admin.ModelAdmin):
    readonly_fields = ("id",)
    list_display = ("machine", "min_quantity", "max_quantity", "price", "currency")
    list_filter = ("machine",)
    search_fields = ("machine__name",)
    autocomplete_fields = ("machine",)
    ordering = ("machine", "min_quantity")
