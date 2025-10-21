# pricing/models
import uuid
from decimal import Decimal
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import PrintCompany
from papers.models import PaperType, ProductionPaperSize
from machines.models import Machine, MachineType
from django.core.exceptions import ValidationError
from django.db.models import Q


# -------------------------------------------------------------------
# DIGITAL PRINT PRICE
# -------------------------------------------------------------------
class DigitalPrintPrice(models.Model):
    """
    Holds single- and double-sided print prices for a given paper type
    on a specific digital press.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        PrintCompany,
        on_delete=models.CASCADE,
        related_name="digital_print_prices",
        help_text=_("The company this pricing belongs to.")
    )
    machine = models.ForeignKey(
        Machine,
        on_delete=models.CASCADE,
        related_name="digital_prices",
        limit_choices_to={"machine_type": MachineType.DIGITAL},
        help_text=_("The digital press this pricing applies to.")
    )
    paper_type = models.ForeignKey(
        PaperType,
        on_delete=models.CASCADE,
        related_name="digital_prices",
        help_text=_("The paper stock this pricing applies to.")
    )
    single_side_price = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text=_("Price per sheet (single-sided).")
    )
    double_side_price = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text=_("Price per sheet (double-sided).")
    )
    currency = models.CharField(max_length=10, default="KES")
    minimum_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    size = models.ForeignKey(
        ProductionPaperSize,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        help_text=_("Default production sheet size for this price (e.g., SRA3).")
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["machine", "paper_type"],
                name="unique_digital_machine_paper"
            )
        ]
        verbose_name = _("Digital Print Price")
        verbose_name_plural = _("Digital Print Prices")
        ordering = ["paper_type__name"]

    def __str__(self):
        return (
            f"{self.machine.name} - {self.paper_type.name}: "
            f"Single {self.single_side_price}{self.currency}, "
            f"Double {self.double_side_price}{self.currency}"
        )

    def save(self, *args, **kwargs):
        if not self.size:
            self.size = ProductionPaperSize.objects.filter(name__iexact="SRA3").first()
        super().save(*args, **kwargs)


# -------------------------------------------------------------------
# LARGE FORMAT PRINT PRICE
# -------------------------------------------------------------------
class LargeFormatPrintPrice(models.Model):
    """
    Defines price per square meter for a specific roll-fed material
    used in large format printing.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(PrintCompany, on_delete=models.CASCADE, related_name="large_format_prices")
    machine = models.ForeignKey(
        Machine,
        on_delete=models.CASCADE,
        related_name="large_format_prices",
        limit_choices_to={"machine_type": MachineType.LARGE_FORMAT},
    )
    material = models.ForeignKey("papers.LargeFormatMaterial", on_delete=models.CASCADE, related_name="prices")

    roll_width_m = models.DecimalField(max_digits=5, decimal_places=2)
    price_per_sq_meter = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default="KES")
    minimum_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["machine", "material", "roll_width_m"],
                name="unique_largeformat_machine_material_width"
            )
        ]

    def __str__(self):
        return f"{self.machine.name} - {self.material.name} ({self.roll_width_m}m): {self.price_per_sq_meter}{self.currency}/sqm"


# -------------------------------------------------------------------
# OFFSET PLATE PRICE
# -------------------------------------------------------------------
class OffsetPlatePrice(models.Model):
    """
    One-time setup cost per plate for offset printing.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(PrintCompany, on_delete=models.CASCADE, related_name="offset_plate_prices")
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name="digital_prices")
    name = models.CharField(max_length=100)
    setup_cost = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.name} ({self.setup_cost} KES)"


# -------------------------------------------------------------------
# OFFSET RUN PRICE
# -------------------------------------------------------------------
class OffsetRunPrice(models.Model):
    """
    Per-sheet running cost for a given paper type on a specific offset press.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(PrintCompany, on_delete=models.CASCADE, related_name="offset_run_prices")
    machine = models.ForeignKey(
        Machine,
        on_delete=models.CASCADE,
        related_name="offset_run_prices",
        limit_choices_to={"machine_type": MachineType.OFFSET},
    )
    paper_type = models.ForeignKey(PaperType, on_delete=models.CASCADE, related_name="offset_run_prices")

    price_per_sheet_per_color = models.DecimalField(max_digits=10, decimal_places=4)
    currency = models.CharField(max_length=10, default="KES")
    minimum_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["machine", "paper_type"],
                name="unique_offset_machine_paper"
            )
        ]

    def __str__(self):
        return f"{self.machine.name} - {self.paper_type.name}: {self.price_per_sheet_per_color}{self.currency}/sheet/color"


# -------------------------------------------------------------------
# SCREEN SETUP PRICE
# -------------------------------------------------------------------
class ScreenSetupPrice(models.Model):
    """
    One-time cost to create a screen (per color).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(PrintCompany, on_delete=models.CASCADE, related_name="screen_setup_prices")
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name="digital_prices")
    name = models.CharField(max_length=100)
    setup_cost = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.name} ({self.setup_cost} KES)"


# -------------------------------------------------------------------
# SCREEN RUN PRICE
# -------------------------------------------------------------------
class ScreenRunPrice(models.Model):
    """
    Running cost per item for screen printing.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(PrintCompany, on_delete=models.CASCADE, related_name="screen_run_prices")
    machine = models.ForeignKey(
        Machine,
        on_delete=models.CASCADE,
        related_name="screen_run_prices",
        limit_choices_to={"machine_type": MachineType.SCREEN},
    )
    run_cost_per_item_per_color = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default="KES")
    minimum_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.machine.name}: {self.run_cost_per_item_per_color}{self.currency}/item/color"


# -------------------------------------------------------------------
# UV DTF PRINT PRICE
# -------------------------------------------------------------------
class UVDTFPrintPrice(models.Model):
    """
    Defines UV DTF film and its price per square meter.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(PrintCompany, on_delete=models.CASCADE, related_name="uvdtf_print_prices")
    machine = models.ForeignKey(
        Machine,
        on_delete=models.CASCADE,
        related_name="uvdtf_prices",
        limit_choices_to={"machine_type": MachineType.UV_DTF},
    )
    material = models.ForeignKey("papers.UVDTFMaterial", on_delete=models.CASCADE, related_name="prices")

    price_per_sq_meter = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default="KES")
    minimum_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.machine.name} - {self.material.name}: {self.price_per_sq_meter}{self.currency}/sqm"


# -------------------------------------------------------------------
# TIERED FINISHING PRICE
# -------------------------------------------------------------------


class TieredFinishingPrice(models.Model):
    """
    Defines tiered (quantity-based) pricing for a specific finishing service
    offered on a machine. Prices adjust based on quantity breakpoints.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    company = models.ForeignKey(
        PrintCompany,
        on_delete=models.CASCADE,
        related_name="tiered_finishing_prices",
        verbose_name=_("Print Company"),
    )

    machine = models.ForeignKey(
        Machine,
        on_delete=models.CASCADE,
        related_name="tiered_finishing_prices",
        verbose_name=_("Machine"),
    )

    service = models.ForeignKey(
        Machine,
        on_delete=models.CASCADE,
        related_name="tiered_finishing_prices",
        verbose_name=_("Finishing Service"),
    )

    # --- Pricing Logic ---
    min_quantity = models.PositiveIntegerField(
        default=1,
        verbose_name=_("Minimum Quantity"),
        help_text=_("Quantity from which this tier's pricing begins."),
    )

    max_quantity = models.PositiveIntegerField(
        default=1,
        verbose_name=_("Maximum Quantity"),
        help_text=_("Quantity up to which this tier's pricing applies."),
    )

    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_("Unit Price"),
        help_text=_("Price per unit within this tier."),
    )

    setup_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name=_("Setup Fee"),
        help_text=_("Optional setup or handling fee for this tier."),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Tiered Finishing Price")
        verbose_name_plural = _("Tiered Finishing Prices")
        ordering = ["company", "machine", "service", "min_quantity"]
        unique_together = ("company", "machine", "service", "min_quantity", "max_quantity")

    def __str__(self):
        return f"{self.service.name} ({self.min_quantity}-{self.max_quantity}) @ {self.unit_price}"

    # --- Business Logic ---
    def applies_to(self, quantity: int) -> bool:
        """Return True if this tier applies to the given quantity."""
        return self.min_quantity <= quantity <= self.max_quantity

    def total_price(self, quantity: int) -> Decimal:
        """Compute total price for a given quantity under this tier."""
        if not self.applies_to(quantity):
            return Decimal("0.00")
        return (Decimal(quantity) * self.unit_price) + self.setup_fee



# -------------------------------------------------------------------
# LAMINATION PRICE
# -------------------------------------------------------------------
class LaminationPrice(models.Model):
    """
    Holds single- and double-sided lamination prices for each lamination type
    (e.g., matte, gloss, velvet) on a specific lamination machine.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        PrintCompany,
        on_delete=models.CASCADE,
        related_name="lamination_prices",
        help_text=_("The company this pricing belongs to.")
    )
    machine = models.ForeignKey(
        Machine,
        on_delete=models.CASCADE,
        related_name="lamination_prices",
        limit_choices_to={"machine_type": MachineType.LAMINATOR},
        help_text=_("The laminator this pricing applies to.")
    )
    lamination_type = models.ForeignKey(
        "papers.LaminationType",  # or PaperType if you already use it for lamination kinds
        on_delete=models.CASCADE,
        related_name="lamination_prices",
        help_text=_("Type of lamination material, e.g., matte, gloss, frost, velvet.")
    )
    size = models.ForeignKey(
        ProductionPaperSize,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        help_text=_("Default production sheet size for this price (e.g., SRA3).")
    )
    single_side_price = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text=_("Price per sheet (single-sided lamination).")
    )
    double_side_price = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text=_("Price per sheet (double-sided lamination).")
    )
    currency = models.CharField(max_length=10, default="KES")
    minimum_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["machine", "lamination_type"],
                name="unique_laminator_machine_laminationtype"
            )
        ]
        verbose_name = _("Lamination Price")
        verbose_name_plural = _("Lamination Prices")
        ordering = ["lamination_type__name"]

    def __str__(self):
        return (
            f"{self.machine.name} - {self.lamination_type.name}: "
            f"Single {self.single_side_price}{self.currency}, "
            f"Double {self.double_side_price}{self.currency}"
        )

    def save(self, *args, **kwargs):
        if not self.size:
            self.size = ProductionPaperSize.objects.filter(name__iexact="SRA3").first()
        super().save(*args, **kwargs)
