import uuid
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator

from machines.models import Machine
from papers.models import FinalPaperSize, PaperType


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

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey("orders.Order", on_delete=models.CASCADE, related_name="deliverables")

    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=255, blank=True, unique=True)
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    page_count = models.PositiveIntegerField(default=1)
    sets = models.PositiveIntegerField(default=1)
    binding = models.CharField(max_length=12, choices=BindingType.choices, default=BindingType.NONE)
    sides = models.CharField(max_length=2, choices=Sidedness.choices, default=Sidedness.DOUBLE)
    size = models.ForeignKey(FinalPaperSize, on_delete=models.PROTECT)

    # Flexible many-to-many relationships with through models
    materials = models.ManyToManyField(
        PaperType,
        through="orders.DeliverableMaterial",
        related_name="deliverables",
    )
    machines = models.ManyToManyField(
        Machine,
        through="orders.DeliverableMachine",
        related_name="deliverables_machines",
    )
    finishings = models.ManyToManyField(
        Machine,
        through="orders.DeliverableFinishing",
        related_name="finishing_jobs",
        blank=True,
    )

    total_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Job Deliverable")
        verbose_name_plural = _("Job Deliverables")

    def __str__(self):
        return f"{self.name} x{self.quantity}"

    def calculate_price(self) -> Decimal:
        from engine.services.costs import compute_total_cost
        try:
            result = compute_total_cost(self)
            return result.get("total_cost", Decimal("0.00"))
        except Exception:
            return Decimal("0.00")

    def save(self, *args, **kwargs):
        from engine.services.costs import compute_total_cost
        try:
            result = compute_total_cost(self)
            self.total_price = result.get("total_cost", Decimal("0.00"))
        except Exception:
            self.total_price = self.calculate_price()
        super().save(*args, **kwargs)


# -------------------------------------------------------------------
# DELIVERABLE MATERIAL
# -------------------------------------------------------------------
class DeliverableMaterial(models.Model):
    deliverable = models.ForeignKey("orders.JobDeliverable", on_delete=models.CASCADE)
    material = models.ForeignKey("papers.PaperType", on_delete=models.PROTECT)
    applies_to = models.CharField(
        max_length=8,
        choices=JobDeliverable.AppliesTo.choices,
        default=JobDeliverable.AppliesTo.WHOLE,
    )
    sides = models.CharField(max_length=2, choices=Sidedness.choices, default=Sidedness.SINGLE)
    sheet_count = models.PositiveIntegerField(default=0)
    unit_price_override = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    class Meta:
        unique_together = ("deliverable", "material", "applies_to")
        verbose_name = _("Deliverable Material")
        verbose_name_plural = _("Deliverable Materials")

    def __str__(self):
        return f"{self.material.name} ({self.get_applies_to_display()})"


# -------------------------------------------------------------------
# DELIVERABLE MACHINE
# -------------------------------------------------------------------
class DeliverableMachine(models.Model):
    deliverable = models.ForeignKey("orders.JobDeliverable", on_delete=models.CASCADE)
    machine = models.ForeignKey("machines.Machine", on_delete=models.PROTECT)
    applies_to = models.CharField(
        max_length=8,
        choices=JobDeliverable.AppliesTo.choices,
        default=JobDeliverable.AppliesTo.WHOLE,
    )
    usage_minutes = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    setup_cost_override = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    class Meta:
        unique_together = ("deliverable", "machine", "applies_to")
        verbose_name = _("Deliverable Machine")
        verbose_name_plural = _("Deliverable Machines")

    def __str__(self):
        return f"{self.machine.name} ({self.get_applies_to_display()})"


# -------------------------------------------------------------------
# DELIVERABLE FINISHINGS
# -------------------------------------------------------------------
class DeliverableFinishing(models.Model):
    deliverable = models.ForeignKey("orders.JobDeliverable", on_delete=models.CASCADE)
    machine = models.ForeignKey("machines.Machine", on_delete=models.PROTECT)
    applies_to = models.CharField(
        max_length=8,
        choices=JobDeliverable.AppliesTo.choices,
        default=JobDeliverable.AppliesTo.WHOLE,
    )
    quantity = models.PositiveIntegerField(null=True, blank=True)
    unit_price_override = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        unique_together = ("deliverable", "machine", "applies_to")
        verbose_name = _("Deliverable Finishing")
        verbose_name_plural = _("Deliverable Finishings")

    def __str__(self):
        return f"{self.machine.name} ({self.get_applies_to_display()})"
