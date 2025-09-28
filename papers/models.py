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
