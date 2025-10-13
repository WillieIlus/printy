from decimal import Decimal
from math import floor, ceil
from typing import Optional

from papers.models import ProductionPaperSize  # This is safe because it’s not circular

# -------------------------------------------------------------------
# UTILITIES
# -------------------------------------------------------------------
def _to_decimal(v) -> Decimal:
    """Convert numeric-like input to Decimal safely."""
    if isinstance(v, Decimal):
        return v
    try:
        return Decimal(str(v))
    except Exception:
        return Decimal("0.00")


# -------------------------------------------------------------------
# GRID FITTING
# -------------------------------------------------------------------
def grid_count(
    av_w: Decimal,
    av_h: Decimal,
    it_w: Decimal,
    it_h: Decimal,
    gutter: Decimal = Decimal("0.00"),
    allow_rotation: bool = True,
) -> int:
    """
    Calculate how many items fit within a given sheet area, considering gutter spacing.
    """

    def fit(w, h, iw, ih, g):
        cols = floor((w + g) / (iw + g)) if iw > 0 else 0
        rows = floor((h + g) / (ih + g)) if ih > 0 else 0
        return max(cols, 0) * max(rows, 0)

    base_fit = fit(av_w, av_h, it_w, it_h, gutter)
    if allow_rotation:
        rot_fit = fit(av_w, av_h, it_h, it_w, gutter)
        return max(base_fit, rot_fit)
    return base_fit


# -------------------------------------------------------------------
# ITEM PER SHEET CALCULATION
# -------------------------------------------------------------------
def items_per_sheet(
    sheet_w_mm: Decimal,
    sheet_h_mm: Decimal,
    item_w_mm: Decimal,
    item_h_mm: Decimal,
    bleed_mm: Decimal = Decimal("0"),
    gutter_mm: Decimal = Decimal("0"),
    allow_rotation: bool = True,
) -> int:
    """Compute how many finished items can be imposed on one production sheet."""
    sheet_w = _to_decimal(sheet_w_mm)
    sheet_h = _to_decimal(sheet_h_mm)
    item_w = _to_decimal(item_w_mm) + (bleed_mm * 2)
    item_h = _to_decimal(item_h_mm) + (bleed_mm * 2)
    gutter = _to_decimal(gutter_mm)
    return grid_count(sheet_w, sheet_h, item_w, item_h, gutter, allow_rotation)


# -------------------------------------------------------------------
# SHEETS NEEDED
# -------------------------------------------------------------------
def sheets_needed(quantity: int, items_per_sheet: int) -> int:
    """Return number of sheets required to print `quantity` items given `items_per_sheet`."""
    if items_per_sheet <= 0:
        items_per_sheet = 1
    return ceil(quantity / items_per_sheet)


# -------------------------------------------------------------------
# BOOKLET IMPOSITION
# -------------------------------------------------------------------
def booklet_imposition(
    quantity: int,
    page_count: int,
    allow_rotation: bool = False,
) -> int:
    """Calculate total inner sheets needed for a booklet."""
    if page_count % 4 != 0:
        page_count += (4 - (page_count % 4))
    if page_count <= 4:
        return quantity
    pages = page_count - 4
    sheets_per_copy = ceil(pages / 4)
    return quantity * sheets_per_copy


# -------------------------------------------------------------------
# JOB SHORTCUTS — LAZY IMPORT FIX 👇
# -------------------------------------------------------------------
def get_job_items_per_sheet(job):
    """
    Shortcut to calculate imposition for a deliverable using its own attributes.
    Lazy import avoids circular dependency.
    """
    from orders.models import JobDeliverable  # lazy import
    sheet = job.material.size
    final_size = job.size

    return items_per_sheet(
        sheet_w_mm=sheet.width_mm,
        sheet_h_mm=sheet.height_mm,
        item_w_mm=final_size.width_mm,
        item_h_mm=final_size.height_mm,
        bleed_mm=_to_decimal(job.bleed_mm),
        gutter_mm=_to_decimal(job.gutter_mm),
        allow_rotation=True,
    )


def get_job_sheets_needed(job):
    """Shortcut for total sheets required for a flat job deliverable."""
    from orders.models import JobDeliverable  # lazy import
    ips = get_job_items_per_sheet(job)
    return sheets_needed(job.quantity, ips)


# engine/services/costs.py
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Optional
from types import SimpleNamespace

from .impositions import sheets_needed, _to_decimal
from pricing.models import DigitalPrintPrice
# ❌ remove this:
# from orders.models import JobDeliverable


# -------------------------------------------------------------------
# CURRENCY FORMATTING
# -------------------------------------------------------------------
def _format_currency(amount: Decimal, currency: str = "KES") -> str:
    amount = (amount or Decimal("0.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{currency} {amount:,}"


# -------------------------------------------------------------------
# SIDEDNESS LOGIC
# -------------------------------------------------------------------
def _get_price_per_sheet(price_obj: DigitalPrintPrice, sidedness: str) -> Decimal:
    sidedness = (sidedness or "").lower()
    if sidedness == "double":
        return _to_decimal(price_obj.double_side_price)
    return _to_decimal(price_obj.single_side_price)


# -------------------------------------------------------------------
# PRICE FINDER
# -------------------------------------------------------------------
def _find_price_for_job(job) -> Optional[DigitalPrintPrice]:
    from orders.models import JobDeliverable   # ✅ lazy import

    if not isinstance(job, JobDeliverable):
        raise TypeError("Expected a JobDeliverable instance")

    return (
        DigitalPrintPrice.objects
        .filter(
            machine=job.machine,
            paper_type=job.material,
            company=job.company
        )
        .first()
    )


# -------------------------------------------------------------------
# DIGITAL PRINT COST CALCULATION
# -------------------------------------------------------------------
def calculate_digital_print_cost(job, price_obj: Optional[DigitalPrintPrice] = None, sheet_count: Optional[int] = None) -> Dict[str, any]:
    from orders.models import JobDeliverable   # ✅ lazy import again

    if not isinstance(job, JobDeliverable):
        raise TypeError("Expected a JobDeliverable instance")

    # 1️⃣ Resolve pricing object
    if price_obj is None:
        price_obj = _find_price_for_job(job)
    if price_obj is None:
        return {"total": Decimal("0.00"), "currency": "KES", "error": "No price found"}

    currency = price_obj.currency

    # 2️⃣ Resolve sheet count
    if sheet_count is None:
        sheet_count = job.sheet_count or 0
    if sheet_count <= 0:
        ips = job.items_per_sheet or 1
        sheet_count = sheets_needed(job.quantity, ips)

    # 3️⃣ Price per sheet
    unit_price = _get_price_per_sheet(price_obj, job.sidedness)

    # 4️⃣ Compute total
    total = unit_price * _to_decimal(sheet_count)

    # 5️⃣ Minimum charge
    minimum = _to_decimal(price_obj.minimum_charge)
    if total < minimum:
        total = minimum

    return {
        "sheets": sheet_count,
        "unit_price": unit_price,
        "minimum_charge": minimum,
        "currency": currency,
        "total": total,
        "formatted": _format_currency(total, currency),
        "pricing_source": price_obj.id,
    }


from decimal import Decimal
from engine.services import impositions

def compute_total_cost(deliverable, price_obj=None):
    """
    Compute total printing cost for a deliverable.
    Uses DigitalPrintPrice rows (single_side_price / double_side_price).
    """
    # safe lazy import for model (handles odd file placement)
    try:
        from pricing.models import DigitalPrintPrice
    except Exception:
        try:
            from pricing.admin import DigitalPrintPrice
        except Exception:
            DigitalPrintPrice = None

    qty = getattr(deliverable, "quantity", 0) or 0
    final_size = getattr(deliverable, "size", None)

    # Accept both inner_machine / machine and inner_material / material
    machine = getattr(deliverable, "inner_machine", None) or getattr(deliverable, "machine", None)
    paper = getattr(deliverable, "inner_material", None) or getattr(deliverable, "material", None)

    bleed = getattr(deliverable, "bleed_mm", 3)
    gutter = getattr(deliverable, "gutter_mm", 5)
    margin = getattr(deliverable, "gripper_mm", 10)

    if not final_size or not machine or not paper:
        return {
            "total_cost": Decimal("0.00"),
            "total_cost_formatted": "KES 0.00",
            "details": "Missing machine, paper, or size"
        }

    # 1) How many items fit per sheet (use machine's sheet dims)
    # Ensure machine has sheet_width_mm / sheet_height_mm attributes (or fallback to supported size)
    sheet_w = getattr(machine, "sheet_width_mm", None)
    sheet_h = getattr(machine, "sheet_height_mm", None)

    if sheet_w is None or sheet_h is None:
        # attempt to pick first supported size object
        try:
            first_supported = machine.supported_sizes.first()
            if first_supported:
                sheet_w = first_supported.width_mm
                sheet_h = first_supported.height_mm
        except Exception:
            sheet_w = None
            sheet_h = None

    if sheet_w is None or sheet_h is None:
        return {
            "total_cost": Decimal("0.00"),
            "total_cost_formatted": "KES 0.00",
            "details": "Machine production sheet size unknown"
        }

    per_sheet = impositions.items_per_sheet(
        sheet_w_mm=sheet_w,
        sheet_h_mm=sheet_h,
        item_w_mm=final_size.width_mm,
        item_h_mm=final_size.height_mm,
        bleed_mm=bleed,
        gutter_mm=gutter,
        margin_mm=margin,
    )

    if per_sheet <= 0:
        return {
            "total_cost": Decimal("0.00"),
            "total_cost_formatted": "KES 0.00",
            "details": "Item does not fit on production sheet"
        }

    # 2) Compute sheets needed
    sheets = impositions.sheets_needed(qty, per_sheet)

    # If Pricing model is not importable, bail
    if DigitalPrintPrice is None:
        return {
            "total_cost": Decimal("0.00"),
            "total_cost_formatted": "KES 0.00",
            "details": "Pricing model unavailable"
        }

    # 3) Try to find a matching price row.
    # Prefer exact match machine + paper_type (paper field in model is 'paper_type')
    price_row = (
        DigitalPrintPrice.objects
        .filter(machine=machine, paper_type=paper)
        .first()
    )

    # fallback to match by machine + size (if price.size exists)
    if not price_row:
        price_row = (
            DigitalPrintPrice.objects
            .filter(machine=machine, size=getattr(paper, "size", None))
            .first()
        )

    # fallback to any price for the machine
    if not price_row:
        price_row = DigitalPrintPrice.objects.filter(machine=machine).first()

    if not price_row:
        return {
            "total_cost": Decimal("0.00"),
            "total_cost_formatted": "KES 0.00",
            "details": "No pricing found for this machine-paper combination"
        }

    # Determine sidedness and choose proper per-sheet price
    sided = getattr(deliverable, "sidedness", None)
    sided_code = str(sided).lower() if sided is not None else ""
    if sided_code in ("s2", "double", "d", "duplex", "2", "two"):
        pps = getattr(price_row, "double_side_price", None) or getattr(price_row, "single_side_price", None)
    else:
        pps = getattr(price_row, "single_side_price", None) or getattr(price_row, "double_side_price", None)

    if pps in (None, 0, "", Decimal("0")):
        return {
            "total_cost": Decimal("0.00"),
            "total_cost_formatted": "KES 0.00",
            "details": "No usable per-sheet price found on matched price row"
        }

    price_per_sheet = Decimal(str(pps))
    total_cost = (Decimal(sheets) * price_per_sheet).quantize(Decimal("0.01"))

    return {
        "total_cost": total_cost,
        "total_cost_formatted": f"KES {total_cost:,.2f}",
        "details": f"{sheets} sheets × KES {price_per_sheet:,.2f} per sheet"
    }

# engine/services/summaries.py
"""
Production summary + short cost snippet using the direct-price cost service.
"""

from typing import Optional
from engine.services.impositions import items_per_sheet


# -------------------------------------------------------------------
# FIND SRA3 OR ALTERNATIVE SHEET SIZE
# -------------------------------------------------------------------
def _find_sra3():
    """
    Attempt to find a ProductionPaperSize object for SRA3 or a close match.
    We lazy import to avoid circular import on startup.
    """
    from papers.models import ProductionPaperSize

    qs = ProductionPaperSize.objects.filter(name__iexact="SRA3")
    if qs.exists():
        return qs.first()

    qs = ProductionPaperSize.objects.filter(name__icontains="sra")
    for p in qs:
        n = (p.name or "").lower()
        if "3" in n or "iii" in n:
            return p
    return None


# -------------------------------------------------------------------
# SHEET SIZE RESOLVER
# -------------------------------------------------------------------
def _resolve_sheet_for_deliverable(deliverable):
    """
    Try to find the sheet used to print a deliverable.
    Priority:
      1) deliverable.print_price.size
      2) SRA3 fallback
      3) machine.supported_sizes.first()
      4) material.size
    """
    # 1) price size
    price_obj = getattr(deliverable, "print_price", None)
    if price_obj is not None and getattr(price_obj, "size", None) is not None:
        return price_obj.size, "price.size"

    # 2) sra3 fallback
    sra3 = _find_sra3()
    if sra3:
        return sra3, "SRA3"

    # 3) machine supported sizes
    machine = getattr(deliverable, "machine", None)
    if machine and hasattr(machine, "supported_sizes"):
        try:
            first_supported = machine.supported_sizes.first()
        except Exception:
            first_supported = None
        if first_supported:
            return first_supported, "machine.supported_size"

    # 4) material size
    mat = getattr(deliverable, "material", None)
    if mat:
        try:
            mat_size = getattr(mat, "size", None)
        except Exception:
            mat_size = None
        if mat_size:
            return mat_size, "material.size"

    return None, "none"


# -------------------------------------------------------------------
# MAIN SUMMARY
# -------------------------------------------------------------------
def deliverable_summary(deliverable) -> str:
    """
    Human readable production summary and short cost snippet (direct-price only).
    Example output:
      "Business Cards: 12 pcs fit per SRA3 ... Estimated cost: KES 2,000.00."
    """
    name = getattr(deliverable, "name", "Deliverable")
    qty = getattr(deliverable, "quantity", 0)

    # --- get final size
    final_size = getattr(deliverable, "size", None)
    final_w = getattr(final_size, "width_mm", None) if final_size else None
    final_h = getattr(final_size, "height_mm", None) if final_size else None

    # --- print params
    bleed = getattr(deliverable, "bleed_mm", 3)
    gutter = getattr(deliverable, "gutter_mm", 5)
    gripper = getattr(deliverable, "gripper_mm", 10)

    # --- resolve sheet
    sheet, source = _resolve_sheet_for_deliverable(deliverable)
    if sheet is None:
        return f"{name}: Could not resolve a production sheet size (no price.size, SRA3, machine or material size). Quantity: {qty}."

    # --- booklet?
    is_booklet = bool(getattr(deliverable, "is_booklet", False))
    if is_booklet:
        try:
            from engine.services.costs import compute_sheets_for_deliverable, compute_total_cost
        except Exception:
            return f"{name}: Booklet (cost/imposition services unavailable)."

        sheets_info = compute_sheets_for_deliverable(deliverable, price_obj=getattr(deliverable, "print_price", None))
        pages = int(getattr(deliverable, "page_count", 0) or 0)
        inner = sheets_info.get("sheets", 0) or 0
        cover = sheets_info.get("cover_sheets", 0) or 0
        total = sheets_info.get("total_physical_sheets", inner + cover)

        base_msg = f"{name}: {pages}pp saddle-stitched. Inner run: {inner} sheet(s). Cover run: {cover} sheet(s). Total physical sheets: {total} (sheet source: {source})."

        try:
            cost = compute_total_cost(deliverable, getattr(deliverable, "print_price", None))
            return base_msg + f" Estimated cost: {cost.get('total_cost_formatted', 'KES 0.00')}."
        except Exception:
            return base_msg

    # --- flat job imposition
    items = items_per_sheet(
        sheet_w_mm=getattr(sheet, "width_mm", 0),
        sheet_h_mm=getattr(sheet, "height_mm", 0),
        item_w_mm=final_w or 0,
        item_h_mm=final_h or 0,
        bleed_mm=bleed,
        gutter_mm=gutter,
    )

    if not items or int(items) <= 0:
        return f"{name}: Item ({final_w}×{final_h} mm) does NOT fit on {sheet.name} ({sheet.width_mm}×{sheet.height_mm} mm) even after bleed."

    import math
    sheets = math.ceil(qty / int(items))

    # Basic machine & paper info
    machine = getattr(deliverable, "machine", None)
    paper = getattr(deliverable, "material", None)
    sidedness = getattr(deliverable, "sidedness", "??")
    machine_name = getattr(machine, "name", "None")
    paper_name = getattr(paper, "name", "None")
    sheet_name = getattr(sheet, "name", "Unknown")

    base_msg = (
        f"📄 {name}: {int(items)} pcs fit per {sheet_name} "
        f"({sheet.width_mm}×{sheet.height_mm} mm) | "
        f"🧮 For {qty} pcs → {sheets} sheet(s). (sheet source: {source})\n"
        f"🖨 Machine: {machine_name}\n"
        f"📏 Paper type: {paper_name}\n"
        f"↔️ Sidedness: {sidedness}\n"
        f"🧾 Quantity: {qty}\n"
    )

    # -------------------------------------------
    # 🪙 Pricing lookup and cost calculation
    # -------------------------------------------
    try:
        from printy.models import DigitalPrintPrice  # adjust if your app name is different

        price_obj = DigitalPrintPrice.objects.get(
            machine=machine,
            paper_type=paper,
            company=deliverable.company
        )
    except Exception:
        price_obj = None
        base_msg += "⚠️ No pricing found for this machine-paper combination.\n"

    if price_obj:
        # Handle sidedness mapping
        if str(sidedness).lower().startswith("s"):
            price_per_sheet = price_obj.single_side_price
        else:
            price_per_sheet = price_obj.double_side_price

        total_cost = sheets * price_per_sheet

        # enforce minimum charge if applicable
        if total_cost < price_obj.minimum_charge:
            total_cost = price_obj.minimum_charge

        base_msg += (
            f"💰 Price per sheet: {price_per_sheet:.2f} KES\n"
            f"🧾 Total: {sheets} × {price_per_sheet:.2f} = {total_cost:.2f} KES\n"
        )

    return base_msg


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
    machine = models.ForeignKey(Machine, on_delete=models.PROTECT, related_name="deliverables", limit_choices_to={"machine_type__in": ["DIGITAL", "UV_FLA", "LARGE_FORMAT"]},    )
    material = models.ForeignKey(PaperType, on_delete=models.PROTECT, related_name="deliverables", help_text=_("The paper stock this pricing applies to."))
    sidedness = models.CharField(max_length=2, choices=Sidedness.choices, default=Sidedness.DOUBLE)
    total_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_booklet = models.BooleanField(default=False)
    page_count = models.PositiveIntegerField(default=1, help_text=_("Total pages including cover if booklet"))
    cover_machine = models.ForeignKey(Machine, null=True,blank=True, on_delete=models.PROTECT, related_name="cover_deliverables", limit_choices_to={"machine_type__in": ["DIGITAL", "UV_FLA", "LARGE_FORMAT"]},)
    cover_material = models.ForeignKey(PaperType, null=True, blank=True, on_delete=models.PROTECT, related_name="cover_deliverables", )
    cover_sidedness = models.CharField(max_length=2, choices=Sidedness.choices, default=Sidedness.SINGLE)
    binding = models.CharField(max_length=12, choices=BindingType.choices, default=BindingType.NONE)
    finishings = models.ManyToManyField("pricing.FinishingService", through="orders.DeliverableFinishing", blank=True, related_name="deliverables",)
    source_template = models.ForeignKey("products.ProductTemplate", on_delete=models.SET_NULL, null=True, blank=True, related_name="deliverables", help_text=_("The product template this deliverable is based on, if any."),)
    bleed_mm = models.PositiveIntegerField(default=3)
    gutter_mm = models.PositiveIntegerField(default=2)
    gripper_mm = models.PositiveIntegerField(default=3)
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
        sheets = self._sheets_needed()
        return costs.deliverable_total(self, cover_sheets=cover_sheets, sheets=sheets)

    def _calculate_flat_price(self):
        """Calculates price for non-booklet items."""
        if not self.material or not self.material.size or not self.machine:
            return Decimal("0.00")

        items_ps = impositions.items_per_sheet(
            sheet_w_mm=self.material.size.width_mm,
            sheet_h_mm=self.material.size.height_mm,
            item_w_mm=self.size.width_mm,
            item_h_mm=self.size.height_mm,
            bleed_mm=self.bleed_mm,
            gutter_mm=self.gutter_mm,
        )
        sheets = impositions.sheets_needed(self.quantity, items_ps)

        return costs.digital_section_cost(
            self.machine,
            self.material,
            self.sidedness,
            sheets,
        )

    def calculate_price(self) -> Decimal:
        """Unified method to calculate price based on deliverable type."""
        if self.is_booklet:
            price = self._calculate_booklet_price()
        else:
            price = self._calculate_flat_price()

        return price.quantize(DECIMAL_QUANT, rounding=ROUND_HALF_UP)


    def _final_dims_mm(self):
        return self.size.width_mm, self.size.height_mm

    def _cover_sheets_needed(self) -> int:
        if not self.is_booklet or not self.cover_machine or not self.cover_material:
            return 0
        return impositions.sheets_needed(self.quantity, 1)

    def _sheets_needed(self) -> int:
        if not self.machine or not self.material:
            return 0

        if not self.is_booklet:
            items_ps = impositions.items_per_sheet(
                sheet_w_mm=self.material.size.width_mm,
                sheet_h_mm=self.material.size.height_mm,
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

        pages = pages - 4
        sheets_per_copy = math.ceil(pages / 4.0)
        return self.quantity * sheets_per_copy

    def production_summary(self) -> str:
        return summaries.deliverable_summary(
            deliverable=self,
            cover_sheets=self._cover_sheets_needed(),
            sheets=self._sheets_needed(),
        )
        

    self.inner_machine = getattr(self, "inner_machine", None) or getattr(self, "machine", None)
    self.inner_material = getattr(self, "inner_material", None) or getattr(self, "material", None)


    def save(self, *args, **kwargs):
        # Compute sheet counts using your helpers (safe, non-persistent)
        try:
            sheets = int(self._sheets_needed() or 0)
        except Exception:
            sheets = 0
        try:
            cover_sheets = int(self._cover_sheets_needed() or 0)
        except Exception:
            cover_sheets = 0

        # Attach imposition dict in-memory for costs service to read
        self.imposition = {
            "sheets": sheets,
            "cover_sheets": cover_sheets,
        }

        # Call cost service (which will auto-find a DigitalPrintPrice if print_price missing)
        try:
            from engine.services.costs import compute_total_cost
            info = compute_total_cost(self, getattr(self, "print_price", None))
            self.total_price = info.get("total_cost", self.total_price or 0)
        except Exception:
            # fallback to older calculate_price logic if available
            try:
                if hasattr(self, "calculate_price") and callable(getattr(self, "calculate_price")):
                    self.total_price = self.calculate_price()
            except Exception:
                # swallow, don't break save
                pass

        super().save(*args, **kwargs)



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
