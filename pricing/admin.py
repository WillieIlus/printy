from django.contrib import admin
from .models import (
    DigitalPrintPrice,
    LargeFormatPrintPrice,
    OffsetPlatePrice,
    OffsetRunPrice,
    ScreenSetupPrice,
    ScreenRunPrice,
    UVDTFPrintPrice,
    FinishingService,
    TieredFinishingPrice,
)

# A base admin class for shared price model configurations
class BasePriceAdmin(admin.ModelAdmin):
    """Base admin configuration for common price models."""
    list_display = ('company', 'machine', 'minimum_charge', 'currency')
    list_filter = ('company', 'machine', 'currency')
    search_fields = ('company__name', 'machine__name')
    autocomplete_fields = ('company', 'machine')
    ordering = ('company',)

@admin.register(DigitalPrintPrice)
class DigitalPrintPriceAdmin(BasePriceAdmin):
    """Admin configuration for Digital Print Prices."""
    list_display = ('paper_type', 'machine', 'single_side_price', 'double_side_price', 'company')
    list_filter = ('company', 'machine', 'currency', 'paper_type')
    search_fields = ('company__name', 'machine__name', 'paper_type__name')
    autocomplete_fields = ('company', 'machine', 'paper_type')
    ordering = ('paper_type__name',)

    fieldsets = (
        (None, {
            'fields': ('company', 'machine', 'paper_type')
        }),
        ('Pricing', {
            'fields': (('single_side_price', 'double_side_price'), 'minimum_charge', 'currency')
        }),
    )

@admin.register(LargeFormatPrintPrice)
class LargeFormatPrintPriceAdmin(BasePriceAdmin):
    """Admin configuration for Large Format Print Prices."""
    list_display = ('material', 'machine', 'price_per_sq_meter', 'roll_width_m', 'company')
    list_filter = ('company', 'machine', 'currency', 'material')
    search_fields = ('company__name', 'machine__name', 'material__name')
    autocomplete_fields = ('company', 'machine', 'material')
    ordering = ('material__name',)

@admin.register(OffsetRunPrice)
class OffsetRunPriceAdmin(BasePriceAdmin):
    """Admin configuration for Offset Run Prices."""
    list_display = ('paper_type', 'machine', 'price_per_sheet_per_color', 'company')
    list_filter = ('company', 'machine', 'currency', 'paper_type')
    search_fields = ('company__name', 'machine__name', 'paper_type__name')
    autocomplete_fields = ('company', 'machine', 'paper_type')
    ordering = ('paper_type__name',)

@admin.register(ScreenRunPrice)
class ScreenRunPriceAdmin(BasePriceAdmin):
    """Admin configuration for Screen Run Prices."""
    list_display = ('machine', 'run_cost_per_item_per_color', 'company')

@admin.register(UVDTFPrintPrice)
class UVDTFPrintPriceAdmin(BasePriceAdmin):
    """Admin configuration for UV DTF Print Prices."""
    list_display = ('material', 'machine', 'price_per_sq_meter', 'company')
    list_filter = ('company', 'machine', 'currency', 'material')
    search_fields = ('company__name', 'machine__name', 'material__name')
    autocomplete_fields = ('company', 'machine', 'material')

# Admin configurations for one-time setup costs
class BaseSetupPriceAdmin(admin.ModelAdmin):
    """Base admin for one-time setup costs."""
    list_display = ('name', 'setup_cost', 'company')
    list_filter = ('company',)
    search_fields = ('name', 'company__name')
    autocomplete_fields = ('company',)
    ordering = ('name',)

@admin.register(OffsetPlatePrice)
class OffsetPlatePriceAdmin(BaseSetupPriceAdmin):
    """Admin configuration for Offset Plate Prices."""
    pass

@admin.register(ScreenSetupPrice)
class ScreenSetupPriceAdmin(BaseSetupPriceAdmin):
    """Admin configuration for Screen Setup Prices."""
    pass

# Inline editor for tiered pricing on the Finishing Service page
class TieredFinishingPriceInline(admin.TabularInline):
    """Allows editing tiered prices directly within the Finishing Service admin."""
    model = TieredFinishingPrice
    fields = ('min_quantity', 'max_quantity', 'price', 'currency')
    extra = 1  # Show one empty row for adding a new tier

@admin.register(FinishingService)
class FinishingServiceAdmin(admin.ModelAdmin):
    """Admin configuration for Finishing Services."""
    list_display = ('name', 'company', 'pricing_method', 'calculation_method', 'simple_price', 'minimum_charge')
    list_filter = ('company', 'pricing_method', 'calculation_method')
    search_fields = ('name', 'company__name')
    autocomplete_fields = ('company',)
    inlines = [TieredFinishingPriceInline]

    fieldsets = (
        (None, {
            'fields': ('company', 'name')
        }),
        ('Pricing Logic', {
            'description': "Select 'Simple' to use the 'Simple Price' field below. Select 'Tiered' to add price rows in the 'Tiered Prices' section.",
            'fields': ('pricing_method', 'calculation_method')
        }),
        ('Simple Pricing', {
            'classes': ('collapse',),
            'fields': ('simple_price', 'minimum_charge', 'currency')
        }),
    )

