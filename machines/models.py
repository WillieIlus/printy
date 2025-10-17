#machines/models  
import uuid
from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from core.models import PrintCompany

from papers.models import ProductionPaperSize

    
class MachineType(models.TextChoices):
    DIGITAL = "DIGITAL", _("Digital Press")
    OFFSET = "OFFSET", _("Offset Press")
    SCREEN = "SCREEN", _("Screen Printer")
    LARGE_FORMAT = "LARGE_FORMAT", _("Large Format Printer")
    UV_DTF = "UV_DTF", _("UV DTF Printer")
    UV_FLATBED = "UV_FLA", _("UV Flatbed Printer")
    FLATBED = "FLATBED", _("Flatbed Printer")
    LASER = "LASER", _("Laser Printer")
    ROUTER = "ROUTER", _("Router Printer")
    LAMINATOR = "LAMINATOR", _("Lamination Machine")
    UV = "UV", _("UV Lamination Machine")
    BINDING = "BINDING", _("Binding Machine")
    CUTTER = "CUTTER", _("Cutter")
    FINISHING = "FINISHING", _("Finishing Machine")
    OTHER = "OTHER", _("Other")
    
class Machine(models.Model):
    """
    Represents a specific machine within a print company.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(PrintCompany, on_delete=models.CASCADE, related_name='machine_finishing_services')
    name = models.CharField(max_length=100, help_text=_("A recognizable name for the machine, e.g., 'HP Indigo' or 'Main Laminator'."))
    machine_type = models.CharField(max_length=50, choices=MachineType.choices, default=MachineType.DIGITAL)
    supported_sizes = models.ManyToManyField(        ProductionPaperSize,
        related_name="supported_machines",
        blank=True,
        verbose_name=_("Supported standard sizes")
    )
    supports_client_custom_size = models.BooleanField(
        default=False,
        verbose_name=_("Supports custom sizes")
    )

    class Meta:
        unique_together = ('company', 'name')
        verbose_name = _("Machine")
        verbose_name_plural = _("Machines")

    def __str__(self):
        return f"{self.name} ({self.get_machine_type_display()})"



class FinishingService(models.Model):
    """
    A generic model for post-print services that supports both
    simple (single price) and tiered (quantity-based) pricing.
    """
    class CalculationMethod(models.TextChoices):
        PER_SHEET_SINGLE_SIDED = 'PER_SHEET_SINGLE', _('Per Sheet (Single Side)')
        PER_SHEET_DOUBLE_sided = 'PER_SHEET_DOUBLE', _('Per Sheet (Double Sided)')
        PER_ITEM = 'PER_ITEM', _('Per Final Item')
        PER_SQ_METER = 'PER_SQ_METER', _('Per Square Meter')

    class PricingMethod(models.TextChoices):
        SIMPLE = 'SIMPLE', _('Simple Price')
        TIERED = 'TIERED', _('Tiered by Quantity')

    # --- Core Fields ---
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(PrintCompany, on_delete=models.CASCADE, related_name='finishing_services')
    name = models.CharField(max_length=100, help_text=_("Name of the service, e.g., 'Matt Lamination', 'Saddle-Stitch Binding'."))
    
    # --- Pricing Logic Fields ---
    pricing_method = models.CharField(
        max_length=10,
        choices=PricingMethod.choices,
        default=PricingMethod.SIMPLE,
        help_text=_("Choose 'Simple' for a single price or 'Tiered' for quantity-based price brackets.")
    )
    calculation_method = models.CharField(
        max_length=20,
        choices=CalculationMethod.choices,
        help_text=_("How the price is applied (e.g., per sheet, per item).")
    )
    simple_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("The price for this service if using the 'Simple' pricing method.")
    )
    currency = models.CharField(max_length=10, default="KES")
    minimum_charge = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text=_("The minimum total price for this service on a job.")
    )

    class Meta:
        unique_together = ('company', 'name')
        verbose_name = _("Finishing Service")
        verbose_name_plural = _("Finishing Services")

    def __str__(self):
        return self.name
    