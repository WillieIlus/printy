from django.contrib import admin
from .models import Machine


@admin.register(Machine)
class MachineAdmin(admin.ModelAdmin):
    """
    Admin configuration for Machine model.

    Allows admins to:
    - Filter by company and machine type
    - Search by machine name or company
    - Select supported sizes through a horizontal filter widget
    - Auto-complete company field for performance
    """

    list_display = ("name", "company", "machine_type")
    list_filter = ("company", "machine_type")
    search_fields = ("name", "company__name")
    search_help_text = "Search by machine name or company name"
    ordering = ("company", "name")

    autocomplete_fields = ("company",)
    filter_horizontal = ("supported_sizes",)

    readonly_fields = ("slug",)

    fieldsets = (
        ("Core Info", {
            "fields": ("company", "name", "machine_type", "slug"),
            "description": "Basic machine information. The slug is auto-generated."
        }),
        ("Size Capabilities", {
            "fields": ("supported_sizes", "supports_client_custom_size"),
            "description": "Select supported standard sizes or allow custom sizes."
        }),
        ("Additional Details", {
            "fields": ("description",),
        }),
    )
