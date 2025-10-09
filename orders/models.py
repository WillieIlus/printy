#orders/models.py
import uuid
import math
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator

from machines.models import Machine, MachineType
from papers.models import FinalPaperSize, PaperType, ProductionPaperSize
from engine.services import costs, impositions, summaries


DECIMAL_QUANT = Decimal("0.01")


# -------------------------------------------------------------------
# ORDER
# -------------------------------------------------------------------
class Order(models.Model):
    """Top-level order. Holds metadata and aggregates deliverables."""

    class Status(models.TextChoices):
        PENDING_QUOTE = "pending_quote", _("Pending Quote")
        QUOTE_SENT = "quote_sent", _("Quote Sent")
        QUOTE_ACCEPTED = "quote_accepted", _("Quote Accepted")
        PAID = "paid", _("Paid")
        IN_PRODUCTION = "in_production", _("In Production")
        COMPLETED = "completed", _("Completed")
        CANCELLED = "cancelled", _("Cancelled")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job_ref = models.CharField(_("Job Reference"), max_length=20, unique=True, blank=True)
    client = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="orders",
        help_text=_("The client/user who placed the order."),
    )
    printer = models.ForeignKey(
        "core.PrintCompany",
        on_delete=models.PROTECT,
        related_name="orders",
        help_text=_("The print company assigned or requested for this order."),
    )
    name = models.CharField(max_length=120, help_text=_("Short description e.g. 'Business cards for ACME'"))
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING_QUOTE)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Optional quoted price
    instant_quote_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("order")
        verbose_name_plural = _("orders")

    def save(self, *args, **kwargs):
        if not self.job_ref:
            self.job_ref = f"JOB-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.job_ref} — {self.name} ({self.get_status_display()})"

    def total_price(self) -> Decimal:
        """Sum of all deliverable totals, quantized to 2 decimals."""
        total = sum((d.total_price for d in self.deliverables.all()), Decimal("0.00"))
        return total.quantize(DECIMAL_QUANT, rounding=ROUND_HALF_UP)


# -------------------------------------------------------------------
# ENUMS
# -------------------------------------------------------------------
class BindingType(models.TextChoices):
    NONE = "NONE", _("None")
    SADDLE = "SADDLE", _("Saddle Stitch")
    PERFECT = "PERFECT", _("Perfect Bind")


class Sidedness(models.TextChoices):
    SINGLE = "S1", _("Single-sided")
    DOUBLE = "S2", _("Double-sided")


# -------------------------------------------------------------------
# JOB DELIVERABLE
# -------------------------------------------------------------------
class JobDeliverable(models.Model):
    """
    One deliverable within an order (e.g., booklet, business cards, flyer).
    Stores client choices and calculates its own price upon saving.
    """

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="deliverables")
    name = models.CharField(max_length=120, help_text=_("e.g., 'Book – Title XYZ'"))
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    size = models.ForeignKey(FinalPaperSize, on_delete=models.PROTECT, related_name="deliverables")
    
    #we need to add sidedness so it is refered by the cost service from here instead

    # This field stores the calculated total price.
    total_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Booklet details
    is_booklet = models.BooleanField(default=False)
    page_count = models.PositiveIntegerField(default=1, help_text=_("Total pages including cover if booklet"))

    # Cover specs (booklets only)
    cover_machine = models.ForeignKey(
        Machine,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="cover_deliverables",
        limit_choices_to={"machine_type__in": ["DIGITAL", "UV_FLA", "LARGE_FORMAT"]},
    )
    cover_material = models.ForeignKey(
        PaperType,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="cover_deliverables",
    )
    cover_sidedness = models.CharField(max_length=2, choices=Sidedness.choices, default=Sidedness.SINGLE)

    # Inner specs (used for both booklets AND flat jobs)
    inner_machine = models.ForeignKey(
        Machine,
        on_delete=models.PROTECT,
        related_name="inner_deliverables",
        limit_choices_to={"machine_type__in": ["DIGITAL", "UV_FLA", "LARGE_FORMAT"]},
    )
    inner_material = models.ForeignKey(
        PaperType,
        on_delete=models.PROTECT,
        related_name="inner_deliverables",
    )
    sidedness = models.CharField(max_length=2, choices=Sidedness.choices, default=Sidedness.DOUBLE)

    # Binding & finishing
    binding = models.CharField(max_length=12, choices=BindingType.choices, default=BindingType.NONE)
    finishings = models.ManyToManyField(
        "pricing.FinishingService",
        through="orders.DeliverableFinishing",
        blank=True,
        related_name="deliverables",
    )

    # Optional link to a product template
    source_template = models.ForeignKey(
        "products.ProductTemplate",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deliverables",
        help_text=_("The product template this deliverable is based on, if any."),
    )

    # Imposition overrides
    bleed_mm = models.PositiveIntegerField(default=3)
    gutter_mm = models.PositiveIntegerField(default=5)
    gripper_mm = models.PositiveIntegerField(default=10)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("job deliverable")
        verbose_name_plural = _("job deliverables")

    def __str__(self):
        return f"{self.name} x{self.quantity}"

    # ---------- CALCULATION ----------

    def _calculate_booklet_price(self):
        cover_sheets = self._cover_sheets_needed()
        inner_sheets = self._inner_sheets_needed()
        return costs.deliverable_total(self, cover_sheets=cover_sheets, inner_sheets=inner_sheets)

    def _calculate_flat_price(self):
        """Calculates price for non-booklet items."""
        if not self.inner_material or not self.inner_material.size or not self.inner_machine:
            return Decimal("0.00")

        items_ps = impositions.items_per_sheet(
            sheet_w_mm=self.inner_material.size.width_mm,
            sheet_h_mm=self.inner_material.size.height_mm,
            item_w_mm=self.size.width_mm,
            item_h_mm=self.size.height_mm,
            bleed_mm=self.bleed_mm,
            gutter_mm=self.gutter_mm,
        )
        sheets = impositions.sheets_needed(self.quantity, items_ps)

        return costs.digital_section_cost(
            self.inner_machine,
            self.inner_material,
            self.inner_sidedness,
            sheets,
        )

    def calculate_price(self) -> Decimal:
        """Unified method to calculate price based on deliverable type."""
        if self.is_booklet:
            price = self._calculate_booklet_price()
        else:
            price = self._calculate_flat_price()

        return price.quantize(DECIMAL_QUANT, rounding=ROUND_HALF_UP)

    # def save(self, *args, **kwargs):
    #     """Override save to automatically calculate the price."""
    #     self.total_price = self.calculate_price()
    #     super().save(*args, **kwargs)

    # ---------- HELPERS ----------

    def _final_dims_mm(self):
        return self.size.width_mm, self.size.height_mm

    def _cover_sheets_needed(self) -> int:
        if not self.is_booklet or not self.cover_machine or not self.cover_material:
            return 0
        return impositions.sheets_needed(self.quantity, 1)

    def _inner_sheets_needed(self) -> int:
        if not self.inner_machine or not self.inner_material:
            return 0

        if not self.is_booklet:
            items_ps = impositions.items_per_sheet(
                sheet_w_mm=self.inner_material.size.width_mm,
                sheet_h_mm=self.inner_material.size.height_mm,
                item_w_mm=self.size.width_mm,
                item_h_mm=self.size.height_mm,
                bleed_mm=self.bleed_mm,
                gutter_mm=self.gutter_mm,
            )
            return impositions.sheets_needed(self.quantity, items_ps)

        # Booklet calculation
        pages = self.page_count
        if pages % 4 != 0:
            pages += (4 - (pages % 4))

        if pages <= 4:
            return 0

        inner_pages = pages - 4
        sheets_per_copy = math.ceil(inner_pages / 4.0)
        return self.quantity * sheets_per_copy

    def production_summary(self) -> str:
        return summaries.deliverable_summary(
            deliverable=self,
            cover_sheets=self._cover_sheets_needed(),
            inner_sheets=self._inner_sheets_needed(),
        )
        
    from django.db import models

def save(self, *args, **kwargs):
    # Auto-assign print_price if not set
    if not getattr(self, "print_price", None):
        try:
            from pricing.models import DigitalPrintPrice
            machine = getattr(self, "inner_machine", None)
            material = getattr(self, "inner_material", None)
            qs = DigitalPrintPrice.objects.all()
            # Try exact price.size == material.size
            if machine and material:
                mat_size = getattr(material, "size", None)
                if mat_size:
                    found = qs.filter(machine=machine, size=mat_size).first()
                    if found:
                        self.print_price = found
            # Try machine + paper_type
            if not getattr(self, "print_price", None) and machine and material:
                paper_type = getattr(material, "paper_type", None) or (material if getattr(material, 'name', None) and not getattr(material, 'paper_type', None) else None)
                if paper_type:
                    found = qs.filter(machine=machine, paper_type=paper_type).first()
                    if found:
                        self.print_price = found
            # Fallback to any price for machine
            if not getattr(self, "print_price", None) and machine:
                found = qs.filter(machine=machine).first()
                if found:
                    self.print_price = found
        except Exception:
            pass

    super().save(*args, **kwargs)


# -------------------------------------------------------------------
# DELIVERABLE FINISHINGS
# -------------------------------------------------------------------
class DeliverableFinishing(models.Model):
    """Attach finishing services to a deliverable."""

    class AppliesTo(models.TextChoices):
        COVER = "cover", _("Cover only")
        INNER = "inner", _("Inner pages only")
        BOOK = "book", _("Whole book / assembly")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    deliverable = models.ForeignKey(JobDeliverable, on_delete=models.CASCADE)
    service = models.ForeignKey("pricing.FinishingService", on_delete=models.PROTECT)
    applies_to = models.CharField(max_length=8, choices=AppliesTo.choices, default=AppliesTo.BOOK)
    notes = models.CharField(max_length=200, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["deliverable", "service", "applies_to"],
                name="unique_finishing_per_scope",
            )
        ]
        verbose_name = _("deliverable finishing")
        verbose_name_plural = _("deliverable finishings")

    def __str__(self):
        return f"{self.deliverable} – {self.service.name} ({self.get_applies_to_display()})"
