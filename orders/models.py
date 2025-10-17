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
    """
    One deliverable within an order (e.g., booklet, business cards, flyer).
    Stores client choices and calculates its own price upon saving.
    """

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="deliverables")
    name = models.CharField(max_length=120, help_text=_("e.g., 'Book – Title XYZ'"))
    slug = models.SlugField(_("slug"), max_length=255, blank=True, unique=True, db_index=True)
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    size = models.ForeignKey(FinalPaperSize, on_delete=models.PROTECT, related_name="deliverables")
    machine = models.ForeignKey(Machine, on_delete=models.PROTECT, related_name="job_deliverables", limit_choices_to={"machine_type__in": ["DIGITAL", "UV_FLA", "LARGE_FORMAT"]},)
    material = models.ForeignKey(PaperType, on_delete=models.PROTECT, related_name="deliverables", help_text=_("The paper stock this pricing applies to."),)

    sidedness = models.CharField(max_length=2, choices=Sidedness.choices, default=Sidedness.DOUBLE)
    total_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    is_booklet = models.BooleanField(default=False) 
    page_count = models.PositiveIntegerField(default=1, help_text=_("Total pages including cover if booklet"))

    cover_machine = models.ForeignKey( Machine, null=True, blank=True, on_delete=models.PROTECT, related_name="cover_job_deliverables", limit_choices_to={"machine_type__in": ["DIGITAL", "UV_FLA", "LARGE_FORMAT"]},)
    cover_material = models.ForeignKey( PaperType, null=True, blank=True, on_delete=models.PROTECT, related_name="cover_job_deliverables",)
    cover_sidedness = models.CharField(max_length=2, choices=Sidedness.choices, default=Sidedness.SINGLE)
    binding = models.CharField(max_length=12, choices=BindingType.choices, default=BindingType.NONE)
    finishings = models.ManyToManyField(FinishingService, through="orders.DeliverableFinishing", blank=True, related_name="deliverables" )
    source_template = models.ForeignKey("products.ProductTemplate", on_delete=models.SET_NULL, null=True, blank=True, related_name="deliverables", help_text=_("The product template this deliverable is based on, if any."),)

    bleed_mm = models.PositiveIntegerField(default=3)
    gutter_mm = models.PositiveIntegerField(default=2)
    gripper_mm = models.PositiveIntegerField(default=3)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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

class DeliverableFinishing(models.Model):
    class AppliesTo(models.TextChoices):
        COVER = "cover", _("Cover only")
        INNER = "inner", _("Inner pages only")
        WHOLE = "whole", _("Entire product")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    deliverable = models.ForeignKey(
        "orders.JobDeliverable",
        on_delete=models.CASCADE,
        related_name="deliverable_finishings"
    )
    service = models.ForeignKey(
        FinishingService,
        on_delete=models.PROTECT,
        related_name="applied_to"
    )

    # Finishing specifics
    applies_to = models.CharField(
        max_length=8,
        choices=AppliesTo.choices,
        default=AppliesTo.WHOLE
    )
    sides = models.PositiveIntegerField(default=1)  # 1 or 2 sides
    sets = models.PositiveIntegerField(default=1)   # useful for per-set finishing like cutting
    quantity_override = models.PositiveIntegerField(null=True, blank=True)  # optional custom qty

    # Price tracking (optional but powerful)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    total_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = _("deliverable finishing")
        verbose_name_plural = _("deliverable finishings")
        constraints = [
            models.UniqueConstraint(
                fields=["deliverable", "service", "applies_to"],
                name="unique_deliverable_finishing_scope"
            )
        ]

    def __str__(self):
        return f"{self.deliverable.name} – {self.service.name} ({self.applies_to})"

    def calculate_price(self):
        """
        Centralized pricing logic for each finishing line.
        """
        qty = self.quantity_override or self.deliverable.quantity
        method = self.service.calculation_method

        if method == "PER_SHEET_SINGLE":
            self.total_price = self.service.simple_price * qty
        elif method == "PER_SHEET_DOUBLE":
            self.total_price = self.service.simple_price * qty * self.sides
        elif method == "PER_ITEM":
            self.total_price = self.service.simple_price * qty
        elif method == "PER_SQ_METER":
            # You can pull area from deliverable size here
            area = self.deliverable.size.area_m2()
            self.total_price = self.service.simple_price * qty * area
        else:
            self.total_price = 0

        return self.total_price

    def save(self, *args, **kwargs):
        self.calculate_price()
        super().save(*args, **kwargs)
