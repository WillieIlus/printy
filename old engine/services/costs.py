from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from engine.services.impositions import (
    get_job_items_per_sheet,
    get_job_sheets_needed,
    get_cover_items_per_sheet,
    get_cover_sheets_needed,
    booklet_imposition
)


@dataclass
class CostingResult:
    """
    Standardized result for cost calculation.
    """
    inner_sheets: int
    cover_sheets: int
    inner_cost: Decimal
    cover_cost: Decimal
    finishing_cost: Decimal
    total_cost: Decimal
    notes: str = ""


def _to_decimal(v) -> Decimal:
    if isinstance(v, Decimal):
        return v
    try:
        return Decimal(str(v))
    except Exception:
        return Decimal("0.00")


# -------------------------------------------------------------------
# PRICE FETCHERS (You can extend for different machine types)
# -------------------------------------------------------------------
def get_inner_sheet_price(job) -> Decimal:
    """
    Get the per-sheet price for the inner section of the job.
    Typically pulled from DigitalPrintPrice / LargeFormatPrice / etc.
    """
    machine = job.machine
    material = job.material

    # Example: Digital print
    if machine.machine_type == "DIGITAL":
        digital_price = material.digital_prices.filter(machine=machine).first()
        if digital_price:
            # choose single or double sided price
            if job.sides == "S2":
                return _to_decimal(digital_price.double_side_price)
            return _to_decimal(digital_price.single_side_price)

    # Large Format
    if machine.machine_type == "LARGE_FORMAT":
        large_price = material.prices.filter(machine=machine).first()
        if large_price:
            return _to_decimal(large_price.price_per_sq_meter)

    # UV DTF, Offset, etc. can be extended here...

    return Decimal("0.00")


def get_cover_sheet_price(job) -> Decimal:
    """
    Get the per-sheet price for the cover section of the job.
    If no cover machine/material, return 0.
    """
    if not job.cover_machine or not job.cover_material:
        return Decimal("0.00")

    machine = job.cover_machine
    material = job.cover_material

    if machine.machine_type == "DIGITAL":
        digital_price = material.digital_prices.filter(machine=machine).first()
        if digital_price:
            if job.cover_sides == "S2":
                return _to_decimal(digital_price.double_side_price)
            return _to_decimal(digital_price.single_side_price)

    if machine.machine_type == "LARGE_FORMAT":
        large_price = material.prices.filter(machine=machine).first()
        if large_price:
            return _to_decimal(large_price.price_per_sq_meter)

    return Decimal("0.00")


# -------------------------------------------------------------------
# FINISHING COST
# -------------------------------------------------------------------
def get_finishing_cost(job) -> Decimal:
    """
    Add up finishing service costs (e.g. lamination, binding, punching).
    This can later be extended to use TieredFinishingPrice.
    """
    total = Decimal("0.00")
    for finishing in job.deliverable_finishings.all():
        # If there's a custom override, use it
        if finishing.unit_price_override:
            total += finishing.unit_price_override * (job.quantity or 1)
        else:
            service = finishing.service
            tier = service.finishing_prices.filter(
                min_quantity__lte=job.quantity,
                max_quantity__gte=job.quantity
            ).first()
            if tier:
                total += tier.price
    return total


# -------------------------------------------------------------------
# MAIN COSTING FUNCTION
# -------------------------------------------------------------------
def compute_total_cost(job) -> dict:
    """
    Main entry point: compute the total production cost for a deliverable.
    Handles:
    - Inner sheet imposition + price
    - Cover imposition + price (optional)
    - Finishing
    - Booklet support
    """
    # ✅ Inner sheets
    if job.is_booklet:
        inner_sheets = booklet_imposition(job.quantity, job.page_count)
    else:
        inner_sheets = get_job_sheets_needed(job)

    inner_price_per_sheet = get_inner_sheet_price(job)
    inner_cost = inner_price_per_sheet * inner_sheets

    # ✅ Cover sheets
    cover_sheets = get_cover_sheets_needed(job) or 0
    cover_price_per_sheet = get_cover_sheet_price(job)
    cover_cost = cover_price_per_sheet * cover_sheets

    # ✅ Finishing
    finishing_cost = get_finishing_cost(job)

    total_cost = inner_cost + cover_cost + finishing_cost

    return {
        "inner_sheets": inner_sheets,
        "cover_sheets": cover_sheets,
        "inner_cost": inner_cost,
        "cover_cost": cover_cost,
        "finishing_cost": finishing_cost,
        "total_cost": total_cost,
    }


# -------------------------------------------------------------------
# WRAPPER CLASS — Optional (dataclass)
# -------------------------------------------------------------------
def compute_costing_result(job) -> CostingResult:
    """
    Returns a structured CostingResult dataclass instead of a dict.
    Handy for typed use in APIs and UI.
    """
    data = compute_total_cost(job)
    return CostingResult(
        inner_sheets=data["inner_sheets"],
        cover_sheets=data["cover_sheets"],
        inner_cost=data["inner_cost"],
        cover_cost=data["cover_cost"],
        finishing_cost=data["finishing_cost"],
        total_cost=data["total_cost"],
    )
