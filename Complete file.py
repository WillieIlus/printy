#papers/models.py
from django.db import models
from django.utils.translation import gettext_lazy as _
import uuid


# -------------------------------------------------------------------
# BASE SIZE
# -------------------------------------------------------------------
class BaseSize(models.Model):
    """Abstract base for paper sizes."""

    PRODUCTION = "production"
    FINAL = "final"

    SIZE_TYPE_CHOICES = [
        (PRODUCTION, _("Production")),
        (FINAL, _("Final")),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_("name"), max_length=100)
    width_mm = models.DecimalField(_("width (mm)"), max_digits=10, decimal_places=2)
    height_mm = models.DecimalField(_("height (mm)"), max_digits=10, decimal_places=2)
    size_type = models.CharField(
        _("size type"), max_length=20, choices=SIZE_TYPE_CHOICES
    )

    class Meta:
        abstract = True
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.width_mm}×{self.height_mm} mm)"


# -------------------------------------------------------------------
# PAPER SIZES
# -------------------------------------------------------------------
class ProductionPaperSize(BaseSize):
    """Represents the actual production sheet sizes (e.g., SRA3, B2)."""

    class Meta(BaseSize.Meta):
        verbose_name = _("Printing paper size")
        verbose_name_plural = _("Printing paper sizes")
        unique_together = ("name", "width_mm", "height_mm")


class FinalPaperSize(BaseSize):
    """Represents customer-facing sizes (e.g., Business Card, A3)."""

    class Meta(BaseSize.Meta):
        verbose_name = _("Final size")
        verbose_name_plural = _("Final sizes")
        unique_together = ("name", "width_mm", "height_mm")


# -------------------------------------------------------------------
# MATERIALS
# -------------------------------------------------------------------
class PaperType(models.Model):
    """
    Represents paper stocks and materials used in digital printing.
    Example: 130gsm Gloss Coated, 250gsm Matte, etc.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_("name"), max_length=150)
    gsm = models.PositiveIntegerField(_("gsm"))
    is_coated = models.BooleanField(_("is coated"), default=False)
    color = models.CharField(_("color"), max_length=50, blank=True)
    is_banner = models.BooleanField(
        default=False, help_text=_("True if this is banner material")
    )
    is_special = models.BooleanField(
        default=False, help_text=_("True if this is a special material like Tic Tac")
    )

    size = models.ForeignKey(
        ProductionPaperSize,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        help_text=_("Default sheet size"),
    )


    class Meta:
        verbose_name = _("Digital paper type")
        verbose_name_plural = _("Digital paper types")
        unique_together = ("name", "gsm")

    def __str__(self):
        return f"{self.name} {self.gsm}gsm"


class LargeFormatMaterial(models.Model):
    """
    Represents materials used in large format printing.
    Example: Vinyl, PVC, Canvas, Fabric, Acrylic, etc.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_("name"), max_length=150, unique=True)
    material_type = models.CharField(_("material type"), max_length=100)
    thickness_mm = models.DecimalField(
        _("thickness (mm)"),
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
    )
    width_mm = models.DecimalField(
        _("width (mm)"),
        max_digits=10,
        decimal_places=2,
        help_text=_("The total width of the material in mm."),
    )

    class Meta:
        verbose_name = _("Large format material")
        verbose_name_plural = _("Large format materials")
        unique_together = ("name", "width_mm")

    def __str__(self):
        return f"{self.name} ({self.material_type})"


class UVDTFMaterial(models.Model):
    """
    Represents materials for UV DTF (Direct to Film) printing.
    Example: A/B Film, Transparent Film, Matte Film, etc.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_("name"), max_length=150, unique=True)
    finish = models.CharField(_("finish"), max_length=100, blank=True)

    class Meta:
        verbose_name = _("UV DTF material")
        verbose_name_plural = _("UV DTF materials")

    def __str__(self):
        return self.name


#papers/admin.py
from django.contrib import admin
from .models import (
    ProductionPaperSize,
    FinalPaperSize,
    PaperType,
    LargeFormatMaterial,
    UVDTFMaterial,
)

# A base admin class for shared paper size configurations
class BaseSizeAdmin(admin.ModelAdmin):
    """Base admin configuration for paper size models."""
    list_display = ('name', 'width_mm', 'height_mm')
    search_fields = ('name',)
    ordering = ('name',)
    
    # Organize fields into sections for a cleaner form
    fieldsets = (
        (None, {
            'fields': ('name', ('width_mm', 'height_mm'))
        }),
    )

    def save_model(self, request, obj, form, change):
        """
        Automatically sets the size_type based on the model.
        This field is defined in the abstract BaseSize model but is not
        meant to be edited by the user in the admin panel.
        """
        if isinstance(obj, ProductionPaperSize):
            obj.size_type = self.model.PRODUCTION
        elif isinstance(obj, FinalPaperSize):
            obj.size_type = self.model.FINAL
        super().save_model(request, obj, form, change)

@admin.register(ProductionPaperSize)
class ProductionPaperSizeAdmin(BaseSizeAdmin):
    """Admin configuration for Production Paper Sizes."""
    pass

@admin.register(FinalPaperSize)
class FinalPaperSizeAdmin(BaseSizeAdmin):
    """Admin configuration for Final Paper Sizes."""
    pass

@admin.register(PaperType)
class PaperTypeAdmin(admin.ModelAdmin):
    """Admin configuration for Digital Paper Types."""
    list_display = ('name', 'gsm', 'is_coated', 'is_banner', 'is_special')
    list_filter = ('is_coated', 'is_banner', 'is_special')
    search_fields = ('name', 'gsm')
    ordering = ('name', 'gsm')

    fieldsets = (
        (None, {
            'fields': ('name', 'gsm')
        }),
        ('Properties', {
            'fields': ('is_coated', 'color')
        }),
        ('Special Types', {
            'description': "Flags for special material types.",
            'fields': ('is_banner', 'is_special')
        }),
    )

@admin.register(LargeFormatMaterial)
class LargeFormatMaterialAdmin(admin.ModelAdmin):
    """Admin configuration for Large Format Materials."""
    list_display = ('name', 'material_type', 'thickness_mm', 'width_mm')
    list_filter = ('material_type',)
    search_fields = ('name', 'material_type')
    ordering = ('name',)
    
    fieldsets = (
        (None, {
            'fields': ('name', 'material_type')
        }),
        ('Specifications (mm)', {
            'fields': (('thickness_mm', 'width_mm'),)
        }),
    )

@admin.register(UVDTFMaterial)
class UVDTFMaterialAdmin(admin.ModelAdmin):
    """Admin configuration for UV DTF Materials."""
    list_display = ('name', 'finish')
    search_fields = ('name', 'finish')
    ordering = ('name',)


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
    company = models.ForeignKey(PrintCompany, on_delete=models.CASCADE, related_name='machines')
    name = models.CharField(max_length=100, help_text=_("A recognizable name for the machine, e.g., 'HP Indigo' or 'Main Laminator'."))
    machine_type = models.CharField(max_length=50, choices=MachineType.choices, default=MachineType.DIGITAL)
    supported_sizes = models.ManyToManyField(
        ProductionPaperSize,
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


#machines/admin.py
from django.contrib import admin
from .models import Machine, MachineType


@admin.register(Machine)
class MachineAdmin(admin.ModelAdmin):
    """Admin configuration for Machines."""
    list_display = ('name', 'company', 'machine_type')
    list_filter = ('company', 'machine_type')
    search_fields = ('name', 'company__name')
    ordering = ('company', 'name')
    
    # Use autocomplete for the company foreign key for better performance
    autocomplete_fields = ('company',)
    
    # Use a more user-friendly interface for the many-to-many relationship
    filter_horizontal = ('supported_sizes',)
    
    # Organize the form fields into logical sections
    fieldsets = (
        (None, {
            'fields': ('company', 'name', 'machine_type')
        }),
        ('Size Capabilities', {
            'description': "Select the standard sizes this machine supports, or allow custom sizes.",
            'fields': ('supported_sizes', 'supports_client_custom_size')
        }),
    )



#pricing/admin.py
import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from core.models import PrintCompany
from papers.models import PaperType
from machines.models import Machine, MachineType


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
        help_text=_("The company this pricing belongs to."),
    )
    machine = models.ForeignKey(
        Machine,
        on_delete=models.CASCADE,
        related_name="digital_prices",
        limit_choices_to={"machine_type": MachineType.DIGITAL},
        help_text=_("The digital press this pricing applies to."),
    )
    paper_type = models.ForeignKey(
        PaperType,
        on_delete=models.CASCADE,
        related_name="digital_prices",
        help_text=_("The paper stock this pricing applies to."),
    )
    single_side_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text=_("Price per sheet (single-sided)."),
    )
    double_side_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text=_("Price per sheet (double-sided)."),
    )
    currency = models.CharField(
        max_length=10,
        default="KES",
        help_text=_("Currency for the pricing (e.g., KES, USD)."),
    )
    minimum_charge = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text=_("The minimum total charge for any job using this price."),
    )

    class Meta:
        unique_together = ("machine", "paper_type")
        verbose_name = _("Digital Print Price")
        verbose_name_plural = _("Digital Print Prices")
        ordering = ["paper_type__name"]

    def __str__(self):
        return (
            f"{self.machine.name} - {self.paper_type.name}: "
            f"Single {self.single_side_price}{self.currency}, "
            f"Double {self.double_side_price}{self.currency}"
        )


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

    roll_width_m = models.DecimalField(max_digits=5, decimal_places=2, help_text=_("Width of the roll in meters."))
    price_per_sq_meter = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default="KES")
    minimum_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        unique_together = ("machine", "material", "roll_width_m")

    def __str__(self):
        return f"{self.machine.name} - {self.material.name} ({self.roll_width_m}m): {self.price_per_sq_meter}{self.currency}/sqm"

class OffsetPlatePrice(models.Model):
    """
    One-time setup cost per plate for offset printing.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(PrintCompany, on_delete=models.CASCADE, related_name="offset_plate_prices")
    name = models.CharField(max_length=100, help_text=_("e.g., 'A3+ Plate'"))
    setup_cost = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.name} ({self.setup_cost} KES)"


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
        unique_together = ("machine", "paper_type")

    def __str__(self):
        return f"{self.machine.name} - {self.paper_type.name}: {self.price_per_sheet_per_color}{self.currency}/sheet/color"


class ScreenSetupPrice(models.Model):
    """
    One-time cost to create a screen (per color).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(PrintCompany, on_delete=models.CASCADE, related_name="screen_setup_prices")
    name = models.CharField(max_length=100, help_text=_("e.g., 'Standard A3 Screen'"))
    setup_cost = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.name} ({self.setup_cost} KES)"


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

class FinishingService(models.Model):
    """
    Post-print finishing service (simple or tiered pricing).
    """
    class CalculationMethod(models.TextChoices):
        PER_SHEET_SINGLE_SIDED = "PER_SHEET_SINGLE", _("Per Sheet (Single Side)")
        PER_SHEET_DOUBLE_SIDED = "PER_SHEET_DOUBLE", _("Per Sheet (Double Side)")
        PER_ITEM = "PER_ITEM", _("Per Final Item")
        PER_SQ_METER = "PER_SQ_METER", _("Per Square Meter")

    class PricingMethod(models.TextChoices):
        SIMPLE = "SIMPLE", _("Simple Price")
        TIERED = "TIERED", _("Tiered by Quantity")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(PrintCompany, on_delete=models.CASCADE, related_name="finishing_services")
    name = models.CharField(max_length=100)

    pricing_method = models.CharField(max_length=10, choices=PricingMethod.choices, default=PricingMethod.SIMPLE)
    calculation_method = models.CharField(max_length=20, choices=CalculationMethod.choices)

    simple_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=10, default="KES")
    minimum_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        unique_together = ("company", "name")

    def __str__(self):
        return self.name


class TieredFinishingPrice(models.Model):
    """
    Quantity-based price tiers for finishing services.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    service = models.ForeignKey(FinishingService, on_delete=models.CASCADE, related_name="tiered_prices")
    min_quantity = models.PositiveIntegerField()
    max_quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default="KES")

    class Meta:
        ordering = ["min_quantity"]

    def __str__(self):
        return f"{self.service.name}: {self.min_quantity}-{self.max_quantity} @ {self.price}{self.currency}"
    
#pricing/admin.py
from django.contrib import admin
from .models import (
    DigitalPrintPrice,
    LargeFormatPrintPrice,
    OffsetPlatePrice,
    OffsetRunPrice,
    ScreenSetupPrice,
    ScreenRunPrice,
    UVDTFPrintPrice,
    FinishingService,
    TieredFinishingPrice,
)

# A base admin class for shared price model configurations
class BasePriceAdmin(admin.ModelAdmin):
    """Base admin configuration for common price models."""
    list_display = ('company', 'machine', 'minimum_charge', 'currency')
    list_filter = ('company', 'machine', 'currency')
    search_fields = ('company__name', 'machine__name')
    autocomplete_fields = ('company', 'machine')
    ordering = ('company',)

@admin.register(DigitalPrintPrice)
class DigitalPrintPriceAdmin(BasePriceAdmin):
    """Admin configuration for Digital Print Prices."""
    list_display = ('paper_type', 'machine', 'single_side_price', 'double_side_price', 'company')
    list_filter = ('company', 'machine', 'currency', 'paper_type')
    search_fields = ('company__name', 'machine__name', 'paper_type__name')
    autocomplete_fields = ('company', 'machine', 'paper_type')
    ordering = ('paper_type__name',)

    fieldsets = (
        (None, {
            'fields': ('company', 'machine', 'paper_type')
        }),
        ('Pricing', {
            'fields': (('single_side_price', 'double_side_price'), 'minimum_charge', 'currency')
        }),
    )

@admin.register(LargeFormatPrintPrice)
class LargeFormatPrintPriceAdmin(BasePriceAdmin):
    """Admin configuration for Large Format Print Prices."""
    list_display = ('material', 'machine', 'price_per_sq_meter', 'roll_width_m', 'company')
    list_filter = ('company', 'machine', 'currency', 'material')
    search_fields = ('company__name', 'machine__name', 'material__name')
    autocomplete_fields = ('company', 'machine', 'material')
    ordering = ('material__name',)

@admin.register(OffsetRunPrice)
class OffsetRunPriceAdmin(BasePriceAdmin):
    """Admin configuration for Offset Run Prices."""
    list_display = ('paper_type', 'machine', 'price_per_sheet_per_color', 'company')
    list_filter = ('company', 'machine', 'currency', 'paper_type')
    search_fields = ('company__name', 'machine__name', 'paper_type__name')
    autocomplete_fields = ('company', 'machine', 'paper_type')
    ordering = ('paper_type__name',)

@admin.register(ScreenRunPrice)
class ScreenRunPriceAdmin(BasePriceAdmin):
    """Admin configuration for Screen Run Prices."""
    list_display = ('machine', 'run_cost_per_item_per_color', 'company')

@admin.register(UVDTFPrintPrice)
class UVDTFPrintPriceAdmin(BasePriceAdmin):
    """Admin configuration for UV DTF Print Prices."""
    list_display = ('material', 'machine', 'price_per_sq_meter', 'company')
    list_filter = ('company', 'machine', 'currency', 'material')
    search_fields = ('company__name', 'machine__name', 'material__name')
    autocomplete_fields = ('company', 'machine', 'material')

# Admin configurations for one-time setup costs
class BaseSetupPriceAdmin(admin.ModelAdmin):
    """Base admin for one-time setup costs."""
    list_display = ('name', 'setup_cost', 'company')
    list_filter = ('company',)
    search_fields = ('name', 'company__name')
    autocomplete_fields = ('company',)
    ordering = ('name',)

@admin.register(OffsetPlatePrice)
class OffsetPlatePriceAdmin(BaseSetupPriceAdmin):
    """Admin configuration for Offset Plate Prices."""
    pass

@admin.register(ScreenSetupPrice)
class ScreenSetupPriceAdmin(BaseSetupPriceAdmin):
    """Admin configuration for Screen Setup Prices."""
    pass

# Inline editor for tiered pricing on the Finishing Service page
class TieredFinishingPriceInline(admin.TabularInline):
    """Allows editing tiered prices directly within the Finishing Service admin."""
    model = TieredFinishingPrice
    fields = ('min_quantity', 'max_quantity', 'price', 'currency')
    extra = 1  # Show one empty row for adding a new tier

@admin.register(FinishingService)
class FinishingServiceAdmin(admin.ModelAdmin):
    """Admin configuration for Finishing Services."""
    list_display = ('name', 'company', 'pricing_method', 'calculation_method', 'simple_price', 'minimum_charge')
    list_filter = ('company', 'pricing_method', 'calculation_method')
    search_fields = ('name', 'company__name')
    autocomplete_fields = ('company',)
    inlines = [TieredFinishingPriceInline]

    fieldsets = (
        (None, {
            'fields': ('company', 'name')
        }),
        ('Pricing Logic', {
            'description': "Select 'Simple' to use the 'Simple Price' field below. Select 'Tiered' to add price rows in the 'Tiered Prices' section.",
            'fields': ('pricing_method', 'calculation_method')
        }),
        ('Simple Pricing', {
            'classes': ('collapse',),
            'fields': ('simple_price', 'minimum_charge', 'currency')
        }),
    )

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
    inner_sidedness = models.CharField(max_length=2, choices=Sidedness.choices, default=Sidedness.DOUBLE)

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

    def save(self, *args, **kwargs):
        """Override save to automatically calculate the price."""
        self.total_price = self.calculate_price()
        super().save(*args, **kwargs)

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


#pricing/admin.py
from django.contrib import admin
from .models import (
    DigitalPrintPrice,
    LargeFormatPrintPrice,
    OffsetPlatePrice,
    OffsetRunPrice,
    ScreenSetupPrice,
    ScreenRunPrice,
    UVDTFPrintPrice,
    FinishingService,
    TieredFinishingPrice,
)

# A base admin class for shared price model configurations
class BasePriceAdmin(admin.ModelAdmin):
    """Base admin configuration for common price models."""
    list_display = ('company', 'machine', 'minimum_charge', 'currency')
    list_filter = ('company', 'machine', 'currency')
    search_fields = ('company__name', 'machine__name')
    autocomplete_fields = ('company', 'machine')
    ordering = ('company',)

@admin.register(DigitalPrintPrice)
class DigitalPrintPriceAdmin(BasePriceAdmin):
    """Admin configuration for Digital Print Prices."""
    list_display = ('paper_type', 'machine', 'single_side_price', 'double_side_price', 'company')
    list_filter = ('company', 'machine', 'currency', 'paper_type')
    search_fields = ('company__name', 'machine__name', 'paper_type__name')
    autocomplete_fields = ('company', 'machine', 'paper_type')
    ordering = ('paper_type__name',)

    fieldsets = (
        (None, {
            'fields': ('company', 'machine', 'paper_type')
        }),
        ('Pricing', {
            'fields': (('single_side_price', 'double_side_price'), 'minimum_charge', 'currency')
        }),
    )

@admin.register(LargeFormatPrintPrice)
class LargeFormatPrintPriceAdmin(BasePriceAdmin):
    """Admin configuration for Large Format Print Prices."""
    list_display = ('material', 'machine', 'price_per_sq_meter', 'roll_width_m', 'company')
    list_filter = ('company', 'machine', 'currency', 'material')
    search_fields = ('company__name', 'machine__name', 'material__name')
    autocomplete_fields = ('company', 'machine', 'material')
    ordering = ('material__name',)

@admin.register(OffsetRunPrice)
class OffsetRunPriceAdmin(BasePriceAdmin):
    """Admin configuration for Offset Run Prices."""
    list_display = ('paper_type', 'machine', 'price_per_sheet_per_color', 'company')
    list_filter = ('company', 'machine', 'currency', 'paper_type')
    search_fields = ('company__name', 'machine__name', 'paper_type__name')
    autocomplete_fields = ('company', 'machine', 'paper_type')
    ordering = ('paper_type__name',)

@admin.register(ScreenRunPrice)
class ScreenRunPriceAdmin(BasePriceAdmin):
    """Admin configuration for Screen Run Prices."""
    list_display = ('machine', 'run_cost_per_item_per_color', 'company')

@admin.register(UVDTFPrintPrice)
class UVDTFPrintPriceAdmin(BasePriceAdmin):
    """Admin configuration for UV DTF Print Prices."""
    list_display = ('material', 'machine', 'price_per_sq_meter', 'company')
    list_filter = ('company', 'machine', 'currency', 'material')
    search_fields = ('company__name', 'machine__name', 'material__name')
    autocomplete_fields = ('company', 'machine', 'material')

# Admin configurations for one-time setup costs
class BaseSetupPriceAdmin(admin.ModelAdmin):
    """Base admin for one-time setup costs."""
    list_display = ('name', 'setup_cost', 'company')
    list_filter = ('company',)
    search_fields = ('name', 'company__name')
    autocomplete_fields = ('company',)
    ordering = ('name',)

@admin.register(OffsetPlatePrice)
class OffsetPlatePriceAdmin(BaseSetupPriceAdmin):
    """Admin configuration for Offset Plate Prices."""
    pass

@admin.register(ScreenSetupPrice)
class ScreenSetupPriceAdmin(BaseSetupPriceAdmin):
    """Admin configuration for Screen Setup Prices."""
    pass

# Inline editor for tiered pricing on the Finishing Service page
class TieredFinishingPriceInline(admin.TabularInline):
    """Allows editing tiered prices directly within the Finishing Service admin."""
    model = TieredFinishingPrice
    fields = ('min_quantity', 'max_quantity', 'price', 'currency')
    extra = 1  # Show one empty row for adding a new tier

@admin.register(FinishingService)
class FinishingServiceAdmin(admin.ModelAdmin):
    """Admin configuration for Finishing Services."""
    list_display = ('name', 'company', 'pricing_method', 'calculation_method', 'simple_price', 'minimum_charge')
    list_filter = ('company', 'pricing_method', 'calculation_method')
    search_fields = ('name', 'company__name')
    autocomplete_fields = ('company',)
    inlines = [TieredFinishingPriceInline]

    fieldsets = (
        (None, {
            'fields': ('company', 'name')
        }),
        ('Pricing Logic', {
            'description': "Select 'Simple' to use the 'Simple Price' field below. Select 'Tiered' to add price rows in the 'Tiered Prices' section.",
            'fields': ('pricing_method', 'calculation_method')
        }),
        ('Simple Pricing', {
            'classes': ('collapse',),
            'fields': ('simple_price', 'minimum_charge', 'currency')
        }),
    )

