#orders/models.py
import uuid
import math
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator

from machines.models import FinishingService, Machine, MachineType
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
    class AppliesTo(models.TextChoices):
        COVER = "cover", _("Cover only")
        INNER = "inner", _("Inner pages only")
        WHOLE = "whole", _("Entire product")

    applies_to = models.CharField(
        max_length=8,
        choices=AppliesTo.choices,
        default=AppliesTo.WHOLE
    )
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="deliverables")
    name = models.CharField(max_length=120, help_text=_("e.g., 'Book – Title XYZ'"))
    slug = models.SlugField(_("slug"), max_length=255, blank=True, unique=True, db_index=True)
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    size = models.ForeignKey(FinalPaperSize, on_delete=models.PROTECT, related_name="deliverables")
    
    machine = models.ForeignKey(Machine, on_delete=models.PROTECT, related_name="job_deliverables", limit_choices_to={"machine_type__in": ["DIGITAL", "UV_FLA", "LARGE_FORMAT"]},)
    material = models.ForeignKey(PaperType, on_delete=models.PROTECT, related_name="deliverables", help_text=_("The paper stock this pricing applies to."),)
    sides = models.CharField(max_length=2, choices=Sidedness.choices, default=Sidedness.DOUBLE)
    is_booklet = models.BooleanField(default=False)
    cover_machine = models.ForeignKey( Machine, null=True, blank=True, on_delete=models.PROTECT, related_name="cover_job_deliverables", limit_choices_to={"machine_type__in": ["DIGITAL", "UV_FLA", "LARGE_FORMAT"]},)
    cover_material = models.ForeignKey( PaperType, null=True, blank=True, on_delete=models.PROTECT, related_name="cover_job_deliverables",)
    cover_sides = models.CharField(max_length=2, choices=Sidedness.choices, default=Sidedness.SINGLE)
    page_count = models.PositiveIntegerField(default=1, help_text=_("Total pages including cover if booklet"))
    sets = models.PositiveIntegerField(default=1)   # useful for per-set finishing like cutting

    binding = models.CharField(max_length=12, choices=BindingType.choices, default=BindingType.NONE)
    finishings = models.ManyToManyField(FinishingService, through="orders.DeliverableFinishing", blank=True, related_name="deliverables" )
    
    sheets_needed = models.PositiveIntegerField(default=0) #useful to determine number of sheet needed after getting the total items required
    total_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    source_template = models.ForeignKey("products.ProductTemplate", on_delete=models.SET_NULL, null=True, blank=True, related_name="deliverables", help_text=_("The product template this deliverable is based on, if any."),)

    bleed_mm = models.PositiveIntegerField(default=3)
    gutter_mm = models.PositiveIntegerField(default=2)
    gripper_mm = models.PositiveIntegerField(default=3)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("job deliverable")
        verbose_name_plural = _("job deliverables")

    def __str__(self):
        return f"{self.name} x{self.quantity}"

    # -------------------------------------------------------------------
    # SUMMARY + COST DELEGATION
    # -------------------------------------------------------------------
    def production_summary(self) -> str:
        """Readable production + cost summary."""
        from engine.services import summaries
        return summaries.deliverable_summary(self)

    def calculate_price(self) -> Decimal:
        """
        Delegates all cost computation to the engine.services.costs module.
        """
        from engine.services.costs import compute_total_cost
        try:
            result = compute_total_cost(self)
            return result.get("total_cost", Decimal("0.00"))
        except Exception:
            return Decimal("0.00")

    def save(self, *args, **kwargs):
        """
        Overrides save() to auto-calculate and store total_price.
        """
        from engine.services.costs import compute_total_cost
        try:
            result = compute_total_cost(self)
            self.total_price = result.get("total_cost", Decimal("0.00"))
        except Exception:
            # fallback to manual calc
            try:
                self.total_price = self.calculate_price()
            except Exception:
                self.total_price = Decimal("0.00")

        super().save(*args, **kwargs)

# -------------------------------------------------------------------
# DELIVERABLE FINISHINGS
# -------------------------------------------------------------------

# orders/models.py (new)
class DeliverableFinishing(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    deliverable = models.ForeignKey("orders.JobDeliverable", on_delete=models.CASCADE, related_name="deliverable_finishings")
    service = models.ForeignKey("machines.FinishingService", on_delete=models.CASCADE, related_name="deliverable_links")
    applies_to = models.CharField(max_length=8, choices=JobDeliverable.AppliesTo.choices, default=JobDeliverable.AppliesTo.WHOLE)
    quantity = models.PositiveIntegerField(null=True, blank=True,
                                           help_text="Optional override quantity for the finishing calculation.")
    unit_price_override = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        unique_together = ("deliverable", "service", "applies_to")

