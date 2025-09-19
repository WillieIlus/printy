# orders/models.py
import uuid
import math
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator

from papers.models import FinalPaperSize
from engine.services import costs, impositions, summaries


DECIMAL_QUANT = Decimal("0.01")


class Order(models.Model):
    """
    Top-level order. Holds metadata and aggregates deliverables.
    Pricing is delegated to JobDeliverable.
    """
    # user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    # product = models.ForeignKey(Product, on_delete=models.CASCADE) """ i'm not sure if to place it here or should it be in jobDeliverables class"
    custom_notes = models.TextField(blank=True)
    instant_quote_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
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

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("order")
        verbose_name_plural = _("orders")

    def save(self, *args, **kwargs):
        if not self.job_ref:
            self.job_ref = f"JOB-{uuid.uuid4().hex[:8].upper()}"
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.job_ref} — {self.name} ({self.get_status_display()})"

    def total_price(self) -> Decimal:
        """Sum of all deliverable totals, quantized to 2 decimals."""
        total = sum((d.total_price() for d in self.deliverables.all()), Decimal("0.00"))
        return total.quantize(DECIMAL_QUANT, rounding=ROUND_HALF_UP)


# ---------- Deliverables ----------
class BindingType(models.TextChoices):
    NONE = "NONE", _("None")
    SADDLE = "SADDLE", _("Saddle Stitch")
    PERFECT = "PERFECT", _("Perfect Bind")


class Sidedness(models.TextChoices):
    SINGLE = "S1", _("Single-sided")
    DOUBLE = "S2", _("Double-sided")


class JobDeliverable(models.Model):
    """
    One deliverable within an order (e.g., booklet, business cards, flyer).
    Stores client choices and provides helper methods to compute sheets/price.
    """
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="deliverables")
    name = models.CharField(max_length=120, help_text=_("e.g., 'Book – Title XYZ'"))
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])

    # Final/client-facing size (width/height mm)
    size = models.ForeignKey(FinalPaperSize, on_delete=models.PROTECT)

    # Booklet details
    is_booklet = models.BooleanField(default=False)
    page_count = models.PositiveIntegerField(default=1, help_text=_("Total pages including cover if booklet"))

    # Cover specs
    cover_machine = models.ForeignKey(
        "machines.Machine",
        null=True, blank=True,
        on_delete=models.PROTECT,
        related_name="cover_deliverables",
        limit_choices_to={"machine_type__in": ["DIGITAL", "UV_FLA", "LARGE_FORMAT"]},
    )
    cover_material = models.ForeignKey(
        "papers.PaperType",
        null=True, blank=True,
        on_delete=models.PROTECT,
        related_name="cover_deliverables",
    )
    cover_sidedness = models.CharField(max_length=2, choices=Sidedness.choices, default=Sidedness.SINGLE)

    # Inner specs
    inner_machine = models.ForeignKey(
        "machines.Machine",
        null=True, blank=True,
        on_delete=models.PROTECT,
        related_name="inner_deliverables",
        limit_choices_to={"machine_type__in": ["DIGITAL", "UV_FLA", "LARGE_FORMAT"]},
    )
    inner_material = models.ForeignKey(
        "papers.PaperType",
        null=True, blank=True,
        on_delete=models.PROTECT,
        related_name="inner_deliverables",
    )
    inner_sidedness = models.CharField(max_length=2, choices=Sidedness.choices, default=Sidedness.DOUBLE)

    # Binding & finishing
    binding = models.CharField(max_length=12, choices=BindingType.choices, default=BindingType.NONE)
    finishings = models.ManyToManyField(
        "pricing.FinishingService",
        through="orders.DeliverableFinishing",
        blank=True,
        related_name="deliverables",
    )

    # Imposition overrides (mm)
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

    # ---------- Imposition helpers ----------
    def items_per_sheet(self, sheet_w_mm: float, sheet_h_mm: float) -> int:
        final_w, final_h = self._final_dims_mm()
        return impositions.items_per_sheet(
            sheet_w_mm, sheet_h_mm, final_w, final_h,
            bleed_mm=self.bleed_mm, gutter_mm=self.gutter_mm, gripper_mm=self.gripper_mm,
        )

    def sheets_needed(self, sheet_w_mm: float, sheet_h_mm: float, quantity: int) -> int:
        per_sheet = self.items_per_sheet(sheet_w_mm, sheet_h_mm)
        return impositions.sheets_needed(quantity, per_sheet)

    def best_fit_orientation(self, sheet_w_mm: float, sheet_h_mm: float):
        final_w, final_h = self._final_dims_mm()
        return impositions.best_fit_orientation(
            sheet_w_mm, sheet_h_mm, final_w, final_h,
            bleed_mm=self.bleed_mm, gutter_mm=self.gutter_mm, gripper_mm=self.gripper_mm,
        )

    # ---------- Booklet-specific helpers ----------
    def _cover_sheets_needed(self) -> int:
        if not self.is_booklet or not self.cover_machine or not self.cover_material:
            return 0
        return impositions.sheets_needed(self.quantity, items_per_sheet=1)

    def _inner_sheets_needed(self) -> int:
        if not self.is_booklet or not self.inner_machine or not self.inner_material:
            return 0

        pages = self.page_count
        if pages % 4 != 0:
            pages += (4 - (pages % 4))  # round up

        if pages <= 4:
            return 0

        inner_pages = pages - 4
        sheets_per_copy = math.ceil(inner_pages / 4.0)

        return impositions.sheets_needed(self.quantity, items_per_sheet=1) * sheets_per_copy

    def total_price(self) -> Decimal:
        cover_sheets = self._cover_sheets_needed()
        inner_sheets = self._inner_sheets_needed()
        return costs.deliverable_total(self, cover_sheets=cover_sheets, inner_sheets=inner_sheets)

    # ---------- Private helpers ----------
    def _final_dims_mm(self):
        return self.size.width_mm, self.size.height_mm

    def production_summary(self) -> str:
        return summaries.deliverable_summary(
            deliverable=self,
            cover_sheets=self._cover_sheets_needed(),
            inner_sheets=self._inner_sheets_needed(),
        )


class DeliverableFinishing(models.Model):
    """
    Through model to attach a FinishingService to a JobDeliverable and indicate where it applies.
    """

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
            models.UniqueConstraint(fields=["deliverable", "service", "applies_to"], name="unique_finishing_per_scope")
        ]
        verbose_name = _("deliverable finishing")
        verbose_name_plural = _("deliverable finishings")

    def __str__(self):
        return f"{self.deliverable} – {self.service.name} ({self.applies_to})"
