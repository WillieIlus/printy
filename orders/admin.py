from decimal import Decimal, ROUND_HALF_UP
from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Order, JobDeliverable, DeliverableFinishing


# -------------------------------------------------------------------
# HELPER — Currency Formatter
# -------------------------------------------------------------------
def _format_currency(amount: Decimal | None, currency: str = "KES") -> str:
    """Format Decimal as currency (e.g., 'KES 1,234.00')."""
    if amount is None:
        return f"{currency} 0.00"
    try:
        value = Decimal(amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return f"{currency} {value:,}"
    except Exception:
        return f"{currency} 0.00"


# -------------------------------------------------------------------
# INLINE — Deliverable Finishing
# -------------------------------------------------------------------
class DeliverableFinishingInline(admin.StackedInline):
    model = DeliverableFinishing
    autocomplete_fields = ("machine",)
    extra = 1

    fields = (
        "machine",
        "applies_to",
        "quantity",
        "unit_price_override",
        "notes",
    )

    @admin.display(description="Calculated Price (KES)")
    def display_price(self, obj):
        try:
            if hasattr(obj, "calculate_price"):
                price = obj.calculate_price()
                return _format_currency(price)
        except Exception:
            pass
        return "–"

    readonly_fields = ("display_price",)


# -------------------------------------------------------------------
# INLINE — Job Deliverables in Order
# -------------------------------------------------------------------
class JobDeliverableInline(admin.TabularInline):
    model = JobDeliverable
    fields = ("name", "quantity", "size", "display_total_price", "display_summary")
    readonly_fields = ("display_total_price", "display_summary")
    show_change_link = True
    extra = 0

    def has_add_permission(self, request, obj=None):
        return False

    @admin.display(description="Total Price")
    def display_total_price(self, obj):
        return _format_currency(getattr(obj, "total_price", Decimal("0.00")))

    @admin.display(description="Production Summary")
    def display_summary(self, obj):
        from engine.services.summaries import deliverable_summary
        try:
            return deliverable_summary(obj)
        except Exception:
            return "–"


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
        (_("Parties"), {"fields": ("client", "printer")}),
        (_("Notes & Pricing"), {"fields": ("notes", "display_total_price")}),
        (_("Timestamps"), {"fields": ("created_at",)}),
    )

    @admin.display(description="Total Price")
    def display_total_price(self, obj):
        try:
            total = obj.total_price()
            return _format_currency(total)
        except Exception:
            return "–"


# -------------------------------------------------------------------
# JOB DELIVERABLE ADMIN
# -------------------------------------------------------------------
@admin.register(JobDeliverable)
class JobDeliverableAdmin(admin.ModelAdmin):
    list_display = ("name", "order", "quantity", "binding", "sides", "display_total_price")
    list_filter = ("order__printer", "binding", "sides", "size")
    search_fields = ("name", "order__job_ref", "order__name")
    readonly_fields = ("total_price", "display_total_price", "display_summary")
    autocomplete_fields = ("order", "size", "materials", "machines", "finishings")
    inlines = [DeliverableFinishingInline]

    fieldsets = (
        ("Core Details", {"fields": ("order", "name", "quantity", "size", "binding", "sides")}),
        ("Pricing", {"fields": ("total_price", "display_total_price")}),
        ("Summary", {"fields": ("display_summary",)}),
    )

    @admin.display(description="Total Price")
    def display_total_price(self, obj):
        return _format_currency(getattr(obj, "total_price", Decimal("0.00")))

    @admin.display(description="Production Summary")
    def display_summary(self, obj):
        from engine.services.summaries import deliverable_summary
        try:
            return deliverable_summary(obj)
        except Exception:
            return "–"

    def save_model(self, request, obj, form, change):
        """Recalculate total price before saving."""
        try:
            if hasattr(obj, "calculate_price"):
                obj.total_price = obj.calculate_price()
        except Exception:
            pass
        super().save_model(request, obj, form, change)
