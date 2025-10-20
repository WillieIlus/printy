import uuid
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator

from machines.models import Machine
from papers.models import FinalPaperSize, PaperType
# Note: ProductionPaperSize was imported but unused — removed for clarity


# -------------------------------------------------------------------
# ORDER MODEL
# -------------------------------------------------------------------
class Order(models.Model):
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
    instant_quote_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Order")
        verbose_name_plural = _("Orders")

    def save(self, *args, **kwargs):
        if not self.job_ref:
            self.job_ref = f"JOB-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.job_ref} — {self.name} ({self.get_status_display()})"

    def total_price(self) -> Decimal:
        total = sum((d.total_price for d in self.deliverables.all()), Decimal("0.00"))
        return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


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

    applies_to = models.CharField(max_length=8, choices=AppliesTo.choices, default=AppliesTo.WHOLE)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="deliverables")
    name = models.CharField(max_length=120, help_text=_("e.g., 'Book – Title XYZ'"))
    slug = models.SlugField(_("slug"), max_length=255, blank=True, unique=True, db_index=True)
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    size = models.ForeignKey(FinalPaperSize, on_delete=models.PROTECT, related_name="deliverables")

    machine = models.ForeignKey(
        Machine,
        on_delete=models.PROTECT,
        related_name="job_deliverables",
        limit_choices_to={"machine_type__in": ["DIGITAL", "UV_FLA", "LARGE_FORMAT"]},
    )
    material = models.ForeignKey(
        PaperType,
        on_delete=models.PROTECT,
        related_name="deliverables",
        help_text=_("The paper stock this pricing applies to."),
    )
    sides = models.CharField(max_length=2, choices=Sidedness.choices, default=Sidedness.DOUBLE)
    is_booklet = models.BooleanField(default=False)

    cover_machine = models.ForeignKey(
        Machine,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="cover_job_deliverables",
        limit_choices_to={"machine_type__in": ["DIGITAL", "UV_FLA", "LARGE_FORMAT"]},
    )
    cover_material = models.ForeignKey(
        PaperType,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="cover_job_deliverables",
    )
    cover_sides = models.CharField(max_length=2, choices=Sidedness.choices, default=Sidedness.SINGLE)
    page_count = models.PositiveIntegerField(default=1)
    sets = models.PositiveIntegerField(default=1)

    binding = models.CharField(max_length=12, choices=BindingType.choices, default=BindingType.NONE)
    finishings = models.ManyToManyField(
        Machine,
        through="orders.DeliverableFinishing",
        blank=True,
        related_name="deliverables",
    )

    sheets_needed = models.PositiveIntegerField(default=0)
    total_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    source_template = models.ForeignKey(
        "products.ProductTemplate",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deliverables",
    )

    bleed_mm = models.PositiveIntegerField(default=3)
    gutter_mm = models.PositiveIntegerField(default=2)
    gripper_mm = models.PositiveIntegerField(default=3)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Job Deliverable")
        verbose_name_plural = _("Job Deliverables")

    def __str__(self):
        return f"{self.name} x{self.quantity}"

    def production_summary(self) -> str:
        """Readable production + cost summary."""
        from engine.services import summaries
        return summaries.deliverable_summary(self)

    def calculate_price(self) -> Decimal:
        """Delegates all cost computation to the pricing engine."""
        from engine.services.costs import compute_total_cost
        try:
            result = compute_total_cost(self)
            return result.get("total_cost", Decimal("0.00"))
        except Exception:
            return Decimal("0.00")

    def save(self, *args, **kwargs):
        """Auto-calculate and store total price."""
        from engine.services.costs import compute_total_cost
        try:
            result = compute_total_cost(self)
            self.total_price = result.get("total_cost", Decimal("0.00"))
        except Exception:
            self.total_price = self.calculate_price()
        super().save(*args, **kwargs)


# -------------------------------------------------------------------
# DELIVERABLE FINISHINGS
# -------------------------------------------------------------------
class DeliverableFinishing(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    deliverable = models.ForeignKey(
        "orders.JobDeliverable",
        on_delete=models.CASCADE,
        related_name="deliverable_finishings"
    )
    service = models.ForeignKey(
        "machines.Machine",
        on_delete=models.CASCADE,
        related_name="deliverable_links"
    )
    applies_to = models.CharField(
        max_length=8,
        choices=JobDeliverable.AppliesTo.choices,
        default=JobDeliverable.AppliesTo.WHOLE
    )
    quantity = models.PositiveIntegerField(null=True, blank=True)
    unit_price_override = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["deliverable", "service", "applies_to"],
                name="unique_finishing_per_deliverable_service"
            )
        ]

    def __str__(self):
        return f"{self.service.name} for {self.deliverable.name}"
