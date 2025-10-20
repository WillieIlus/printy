from decimal import Decimal, ROUND_HALF_UP
from django.contrib import admin
from .models import Order, JobDeliverable, DeliverableFinishing


# -------------------------------------------------------------------
# HELPER — Currency Formatter
# -------------------------------------------------------------------
def _format_currency(amount: Decimal, currency: str = "KES") -> str:
    """
    Formats a Decimal amount as currency (e.g., KES 1,234.00).
    """
    try:
        value = (Decimal(amount or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return f"{currency} {value:,}"
    except Exception:
        return f"{currency} 0.00"


# -------------------------------------------------------------------
# INLINE — Finishing per Deliverable
# -------------------------------------------------------------------
class DeliverableFinishingInline(admin.StackedInline):
    model = DeliverableFinishing
    autocomplete_fields = ("service",)
    raw_id_fields = ("deliverable",)
    extra = 1

    fields = (
        "deliverable",
        "service",
        "applies_to",
        "quantity",
        "unit_price_override",
        "notes",
    )

    def save_model(self, request, obj, form, change):
        """
        Recalculate finishing cost on save (if applicable).
        """
        try:
            obj.calculate_price()
        except Exception:
            pass
        super().save_model(request, obj, form, change)


# -------------------------------------------------------------------
# INLINE — Deliverables inside Order
# -------------------------------------------------------------------
class JobDeliverableInline(admin.TabularInline):
    model = JobDeliverable
    fields = ("name", "quantity", "size", "display_production_summary", "display_total_price")
    readonly_fields = ("name", "size", "display_production_summary", "display_total_price")
    show_change_link = True
    extra = 0

    def has_add_permission(self, request, obj=None):
        return False

    @admin.display(description="Production Summary")
    def display_production_summary(self, obj):
        from engine.services.summaries import deliverable_summary
        try:
            return deliverable_summary(obj)
        except Exception:
            return "-"

    @admin.display(description="Total Price")
    def display_total_price(self, obj):
        value = getattr(obj, "total_price", None)
        return _format_currency(value) if value is not None else "n/a"


# -------------------------------------------------------------------
# ORDER ADMIN
# -------------------------------------------------------------------
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "job_ref",
        "name",
        "client",
        "printer",
        "status",
        "created_at",
        "display_total_price",
    )
    list_filter = ("status", "printer", "client")
    search_fields = ("job_ref", "name", "client__email", "printer__name")
    ordering = ("-created_at",)
    autocomplete_fields = ("client", "printer")
    readonly_fields = ("job_ref", "created_at", "display_total_price")
    inlines = [JobDeliverableInline]

    fieldsets = (
        (None, {"fields": ("job_ref", "name", "status")}),
        ("Parties Involved", {"fields": ("client", "printer")}),
        ("Pricing & Notes", {"fields": ("display_total_price", "notes")}),
        ("Timestamps", {"fields": ("created_at",)}),
    )

    @admin.display(description="Total Price")
    def display_total_price(self, obj):
        total = Decimal("0.00")
        try:
            for d in obj.deliverables.all():
                total += d.total_price or Decimal("0.00")
        except Exception:
            return "n/a"
        return _format_currency(total)


# -------------------------------------------------------------------
# JOB DELIVERABLE ADMIN
# -------------------------------------------------------------------
@admin.register(JobDeliverable)
class JobDeliverableAdmin(admin.ModelAdmin):
    list_display = ("name", "order", "quantity", "is_booklet", "display_total_price")
    list_filter = ("order__printer", "is_booklet", "size")
    search_fields = ("name", "order__job_ref", "order__name")
    readonly_fields = ("total_price", "display_total_price", "display_production_summary")
    autocomplete_fields = ("order", "size", "cover_machine", "cover_material", "machine", "material")
    inlines = [DeliverableFinishingInline]

    fieldsets = (
        ("Core Details", {"fields": ("order", "name", "quantity", "size")}),
        ("Pricing", {"fields": ("total_price", "display_total_price", "display_production_summary")}),
        ("Primary Specs", {"fields": ("machine", "material", "sides")}),
        ("Booklet Specs", {"classes": ("collapse",), "fields": ("is_booklet", "page_count", "binding")}),
        ("Cover Specs", {"classes": ("collapse",), "fields": ("cover_machine", "cover_material", "cover_sides")}),
        ("Imposition Settings", {"classes": ("collapse",), "fields": ("bleed_mm", "gutter_mm", "gripper_mm")}),
    )

    @admin.display(description="Total Price")
    def display_total_price(self, obj):
        return _format_currency(getattr(obj, "total_price", Decimal("0.00")))

    @admin.display(description="Production Summary")
    def display_production_summary(self, obj):
        from engine.services.summaries import deliverable_summary
        try:
            return deliverable_summary(obj)
        except Exception:
            return "-"

    def save_model(self, request, obj, form, change):
        """
        Recalculate total price on save.
        """
        try:
            obj.total_price = obj.calculate_price()
        except Exception:
            pass
        super().save_model(request, obj, form, change)
