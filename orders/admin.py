# orders/admin.py
from decimal import Decimal, ROUND_HALF_UP
from django.contrib import admin
from django.utils.html import format_html

from .models import Order, JobDeliverable, DeliverableFinishing


def _format_currency(amount: Decimal, currency: str = "KES") -> str:
    try:
        a = (Decimal(amount or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return f"{currency} {a:,}"
    except Exception:
        return f"{currency} 0.00"


class DeliverableFinishingInline(admin.StackedInline):
    model = DeliverableFinishing
    autocomplete_fields = ("service",)
    extra = 1


class JobDeliverableInline(admin.TabularInline):
    """
    Compact inline for viewing JobDeliverables on the Order page.
    Shows production summary and total price as read-only columns.
    """
    model = JobDeliverable
    fields = ("name", "quantity", "size", "display_production_summary", "display_total_price")
    readonly_fields = ("name", "size", "display_production_summary", "display_total_price")
    show_change_link = True
    extra = 0

    def has_add_permission(self, request, obj=None):
        # keep your previous behaviour (no add via inline)
        return False

    def has_delete_permission(self, request, obj=None):
        return True

    @admin.display(description="Production Summary")
    def display_production_summary(self, obj):
        try:
            # lazy import to avoid circular import at startup
            from engine.services.summaries import deliverable_summary
        except Exception:
            return "summary unavailable"
        try:
            return deliverable_summary(obj)
        except Exception as e:
            return f"error: {e}"

    @admin.display(description="Total Price")
    def display_total_price(self, obj):
        """
        Inline total price: prefer compute_total_cost (direct-price service).
        """
        try:
            from engine.services.costs import compute_total_cost
        except Exception:
            # fallback to stored attribute
            val = getattr(obj, "total_price", None)
            if val is None:
                return "n/a"
            return _format_currency(val)

        try:
            price_info = compute_total_cost(obj, getattr(obj, "print_price", None))
            return price_info.get("total_cost_formatted", _format_currency(Decimal("0.00")))
        except Exception:
            # last-resort fallback
            val = getattr(obj, "total_price", None)
            return _format_currency(val if val is not None else Decimal("0.00"))


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("job_ref", "name", "client", "printer", "status", "created_at", "display_total_price")
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
        """
        Order-level total: sum deliverable totals (computed using direct-price cost service).
        Falls back to model method/attribute if service unavailable.
        """
        try:
            from engine.services.costs import compute_total_cost
        except Exception:
            # fallback to order model's own calculation if available
            try:
                total = getattr(obj, "total_price", None)
                if callable(total):
                    return _format_currency(total())
                return _format_currency(total)
            except Exception:
                return "n/a"

        total = Decimal("0.00")
        warnings = []
        try:
            # Use the related manager for deliverables; iterate and sum
            for d in obj.jobdeliverable_set.all():
                try:
                    res = compute_total_cost(d, getattr(d, "print_price", None))
                    total += res.get("total_cost", Decimal("0.00")) or Decimal("0.00")
                    if res.get("warnings"):
                        warnings.extend(res.get("warnings"))
                except Exception:
                    # if computing a specific deliverable fails, skip and continue
                    continue
        except Exception:
            # if iteration fails, fallback to model-level total_price
            try:
                return _format_currency(obj.total_price())
            except Exception:
                return "n/a"

        return _format_currency(total)


@admin.register(JobDeliverable)
class JobDeliverableAdmin(admin.ModelAdmin):
    list_display = ("name", "order", "quantity", "is_booklet", "display_total_price")
    list_filter = ("order__printer", "is_booklet", "size")
    search_fields = ("name", "order__job_ref", "order__name")

    readonly_fields = ("total_price", "display_total_price", "display_production_summary")

    autocomplete_fields = ("order", "size", "cover_machine", "cover_material", "inner_machine", "inner_material")
    inlines = [DeliverableFinishingInline]

    fieldsets = (
        ("Core Details", {"fields": ("order", "name", "quantity", "size")}),
        ("Calculations", {"fields": ("total_price", "display_total_price", "display_production_summary")}),
        ("Primary Specifications (for all jobs)", {"fields": ("inner_machine", "inner_material", "sidedness")}),
        ("Booklet Specifications", {"classes": ("collapse",), "fields": ("is_booklet", "page_count", "binding")}),
        ("Cover Specifications (Booklets Only)", {"classes": ("collapse",), "fields": ("cover_machine", "cover_material", "cover_sidedness")}),
        ("Imposition Settings (Advanced)", {"classes": ("collapse",), "fields": ("bleed_mm", "gutter_mm", "gripper_mm")}),
    )

    @admin.display(description="Total Price")
    def display_total_price(self, obj):
        """
        Display total price for this deliverable, computed via direct-price cost service.
        """
        try:
            from engine.services.costs import compute_total_cost
        except Exception:
            val = getattr(obj, "total_price", None)
            if val is None:
                return "n/a"
            return _format_currency(val)

        try:
            res = compute_total_cost(obj, getattr(obj, "print_price", None))
            return res.get("total_cost_formatted", _format_currency(Decimal("0.00")))
        except Exception:
            # fallback to stored total_price
            val = getattr(obj, "total_price", None)
            return _format_currency(val if val is not None else Decimal("0.00"))

    @admin.display(description="Production Summary")
    def display_production_summary(self, obj):
        try:
            from engine.services.summaries import deliverable_summary
        except Exception:
            return "-"
        try:
            return deliverable_summary(obj)
        except Exception:
            return "-"

    def save_model(self, request, obj, form, change):
        """
        Admin: compute imposition/sheets then compute cost and persist total_price.
        Uses engine.services.costs.compute_total_cost which will auto-find a price row
        when obj.print_price is None.
        """
        try:
            # 1) ensure imposition / sheet counts are available on the object
            inner_sheets = 0
            cover_sheets = 0
            try:
                inner_sheets = int(obj._inner_sheets_needed() or 0)
            except Exception:
                inner_sheets = 0
            try:
                cover_sheets = int(obj._cover_sheets_needed() or 0)
            except Exception:
                cover_sheets = 0

            # Attach a minimal imposition dict the cost service will pick up
            obj.imposition = {
                "inner_sheets": inner_sheets,
                "cover_sheets": cover_sheets,
                # For non-booklet jobs you can also include items_per_sheet if available:
                # "items_per_sheet": some_value
            }

            # 2) compute total cost (compute_total_cost will try to auto-find DigitalPrintPrice)
            from engine.services.costs import compute_total_cost
            info = compute_total_cost(obj, getattr(obj, "print_price", None))
            # info['total_cost'] is a Decimal
            obj.total_price = info.get("total_cost", obj.total_price or 0)
        except Exception:
            # fallback: try existing calculate_price method if present
            try:
                if hasattr(obj, "calculate_price") and callable(getattr(obj, "calculate_price")):
                    obj.total_price = obj.calculate_price()
            except Exception:
                # do not raise during admin save
                pass

        super().save_model(request, obj, form, change)

