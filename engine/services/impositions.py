#services/impositions.py
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
