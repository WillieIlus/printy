#services/costs.py
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Optional

from engine.services.impositions import sheets_needed, _to_decimal


# -------------------------------------------------------------------
# HELPER: Format currency
# -------------------------------------------------------------------
def _format_currency(amount: Decimal, currency: str = "KES") -> str:
    amount = (amount or Decimal("0.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{currency} {amount:,}"


# -------------------------------------------------------------------
# HELPER: Determine single/double side price
# -------------------------------------------------------------------
def _get_price_per_sheet(price_obj, sidedness: str) -> Decimal:
    sidedness = (sidedness or "").lower()
    if sidedness in ("s2", "double", "duplex", "2", "two", "d"):
        return _to_decimal(price_obj.double_side_price)
    return _to_decimal(price_obj.single_side_price)


# -------------------------------------------------------------------
# Find matching DigitalPrintPrice for a given JobDeliverable
# -------------------------------------------------------------------
def _find_price_for_job(job) -> Optional["DigitalPrintPrice"]:
    from orders.models import JobDeliverable  # lazy import
    from pricing.models import DigitalPrintPrice

    if not isinstance(job, JobDeliverable):
        raise TypeError("Expected a JobDeliverable instance")

    return (
        DigitalPrintPrice.objects
        .filter(
            machine=job.machine,
            paper_type=job.material,
            company=job.company,
        )
        .first()
    )


# -------------------------------------------------------------------
# MAIN: Compute digital printing cost (for any deliverable)
# -------------------------------------------------------------------
def compute_total_cost(deliverable, price_obj=None) -> Dict[str, any]:
    """
    Computes total printing cost for a deliverable:
      total_cost = price_per_sheet × sheets_needed
    Uses machine.sheet_width_mm / sheet_height_mm and material (paper) size.
    """

    from engine.services import impositions

    try:
        from pricing.models import DigitalPrintPrice
    except Exception:
        return {
            "total_cost": Decimal("0.00"),
            "total_cost_formatted": "KES 0.00",
            "details": "Pricing model unavailable",
        }

    qty = getattr(deliverable, "quantity", 0) or 0
    final_size = getattr(deliverable, "size", None)
    machine = getattr(deliverable, "machine", None)
    paper = getattr(deliverable, "material", None)
    sidedness = getattr(deliverable, "sidedness", "single")

    bleed = getattr(deliverable, "bleed_mm", 3)
    gutter = getattr(deliverable, "gutter_mm", 5)
    margin = getattr(deliverable, "gripper_mm", 10)

    # --- Validation
    if not (machine and paper and final_size):
        return {
            "total_cost": Decimal("0.00"),
            "total_cost_formatted": "KES 0.00",
            "details": "Missing machine, paper, or final size",
        }

    # --- Determine machine's production sheet size
    sheet_w = getattr(machine, "sheet_width_mm", None)
    sheet_h = getattr(machine, "sheet_height_mm", None)

    if not sheet_w or not sheet_h:
        try:
            first_supported = machine.supported_sizes.first()
            if first_supported:
                sheet_w = first_supported.width_mm
                sheet_h = first_supported.height_mm
        except Exception:
            sheet_w, sheet_h = None, None

    if not sheet_w or not sheet_h:
        return {
            "total_cost": Decimal("0.00"),
            "total_cost_formatted": "KES 0.00",
            "details": "Machine production sheet size unknown",
        }

    # --- Compute how many items fit per sheet
    per_sheet = impositions.items_per_sheet(
        sheet_w_mm=sheet_w,
        sheet_h_mm=sheet_h,
        item_w_mm=getattr(final_size, "width_mm", 0),
        item_h_mm=getattr(final_size, "height_mm", 0),
        bleed_mm=bleed,
        gutter_mm=gutter,
        allow_rotation=True,
    )

    if per_sheet <= 0:
        return {
            "total_cost": Decimal("0.00"),
            "total_cost_formatted": "KES 0.00",
            "details": "Item does not fit on production sheet",
        }

    # --- Compute total sheets needed
    sheets = impositions.sheets_needed(qty, per_sheet)

    # --- Get price row
    price_row = (
        DigitalPrintPrice.objects
        .filter(machine=machine, paper_type=paper)
        .first()
        or DigitalPrintPrice.objects.filter(machine=machine).first()
    )

    if not price_row:
        return {
            "total_cost": Decimal("0.00"),
            "total_cost_formatted": "KES 0.00",
            "details": "No pricing found for this machine-paper combination",
        }

    # --- Determine correct per-sheet price
    price_per_sheet = _get_price_per_sheet(price_row, sidedness)

    if price_per_sheet <= 0:
        return {
            "total_cost": Decimal("0.00"),
            "total_cost_formatted": "KES 0.00",
            "details": "No usable price per sheet found",
        }

    # --- Compute total cost
    total_cost = (Decimal(sheets) * price_per_sheet).quantize(Decimal("0.01"))

    # --- Enforce minimum charge
    minimum = _to_decimal(getattr(price_row, "minimum_charge", 0))
    if total_cost < minimum:
        total_cost = minimum

    return {
        "total_cost": total_cost,
        "total_cost_formatted": f"KES {total_cost:,.2f}",
        "details": f"{sheets} sheets × KES {price_per_sheet:,.2f} per sheet",
    }


# -------------------------------------------------------------------
# Optional lower-level function (for internal use)
# -------------------------------------------------------------------
def calculate_digital_print_cost(job, price_obj=None, sheet_count=None) -> Dict[str, any]:
    """
    Lower-level function used internally for cases where you already
    know sheet_count and price object.
    """
    if price_obj is None:
        price_obj = _find_price_for_job(job)
    if price_obj is None:
        return {"total": Decimal("0.00"), "currency": "KES", "error": "No price found"}

    currency = getattr(price_obj, "currency", "KES")
    unit_price = _get_price_per_sheet(price_obj, getattr(job, "sidedness", "single"))

    if sheet_count is None:
        qty = getattr(job, "quantity", 0)
        ips = getattr(job, "items_per_sheet", 1) or 1
        sheet_count = sheets_needed(qty, ips)

    total = _to_decimal(unit_price) * _to_decimal(sheet_count)

    minimum = _to_decimal(getattr(price_obj, "minimum_charge", 0))
    if total < minimum:
        total = minimum

    return {
        "sheets": sheet_count,
        "unit_price": unit_price,
        "minimum_charge": minimum,
        "currency": currency,
        "total": total,
        "formatted": _format_currency(total, currency),
        "pricing_source": getattr(price_obj, "id", None),
    }
