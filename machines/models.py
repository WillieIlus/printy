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

