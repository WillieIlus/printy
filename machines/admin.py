# machines/admin.py
from django.contrib import admin

from pricing.admin import TieredFinishingPriceInline
from .models import Machine, MachineType, FinishingService


@admin.register(Machine)
class MachineAdmin(admin.ModelAdmin):
    """Admin configuration for Machines."""
    list_display = ('name', 'company', 'machine_type')
    list_filter = ('company', 'machine_type')
    search_fields = ('name', 'company__name')
    ordering = ('company', 'name')
    autocomplete_fields = ('company',)
    filter_horizontal = ('supported_sizes',)

    fieldsets = (
        (None, {
            'fields': ('company', 'name', 'machine_type')
        }),
        ('Size Capabilities', {
            'description': "Select the standard sizes this machine supports, or allow custom sizes.",
            'fields': ('supported_sizes', 'supports_client_custom_size')
        }),
    )


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

