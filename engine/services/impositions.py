"""
engine/services/impositions.py

Imposition helpers for placing final items/pages on production sheets.

Functions:
- items_layout(...) -> Dict[str, Any]
    detailed layout (cols, rows, count, orientation, effective sizes)
- items_per_sheet(...) -> int
    simple wrapper returning the number of items (final pieces) that fit on a single sheet side
- sheets_needed(quantity, items_per_sheet) -> int
    ceil(quantity / items_per_sheet) with safe fallbacks
- booklet_imposition(...) -> Dict[str, Any]
    booklet-aware calculation for saddle-stitched booklets:
      - handles duplex
      - rounds pages to signature multiples (default 4)
      - supports separate cover runs (different sheet / bleed / margins)
      - returns inner/cover/total sheets and meta useful for pricing
"""

from decimal import Decimal
import math
from typing import Dict, Any, Optional
from math import ceil


def _to_decimal(v) -> Decimal:
    """Convert numeric-like input to Decimal safely."""
    if isinstance(v, Decimal):
        return v
    try:
        return Decimal(str(v))
    except Exception:
        return Decimal(0)


def items_layout(
    sheet_w_mm,
    sheet_h_mm,
    item_w_mm,
    item_h_mm,
    bleed_mm: float = 3,
    gutter_mm: float = 5,
    margin_mm: float = 10,
    allow_rotation: bool = True,
) -> Dict[str, Any]:

    sw = _to_decimal(sheet_w_mm)
    sh = _to_decimal(sheet_h_mm)
    iw = _to_decimal(item_w_mm)
    ih = _to_decimal(item_h_mm)
    bleed = _to_decimal(bleed_mm)
    gutter = _to_decimal(gutter_mm)
    margin = _to_decimal(margin_mm)

    # Effective item size includes bleed on both sides
    eff_w = iw + (bleed * 2)
    eff_h = ih + (bleed * 2)

    # Available space after margins for cropmarks/gripper
    avail_w = sw - (margin * 2)
    avail_h = sh - (margin * 2)

    # If available space non-positive, nothing fits
    if avail_w <= 0 or avail_h <= 0:
        return {
            "count": 0,
            "cols": 0,
            "rows": 0,
            "rotated": False,
            "effective_item_w_mm": eff_w,
            "effective_item_h_mm": eff_h,
            "available_w_mm": avail_w,
            "available_h_mm": avail_h,
            "sheet_w_mm": sw,
            "sheet_h_mm": sh,
            "bleed_mm": bleed,
            "gutter_mm": gutter,
            "margin_mm": margin,
        }

    def grid_count(av_w: Decimal, av_h: Decimal, it_w: Decimal, it_h: Decimal, g: Decimal):
        """
        Compute how many items fit in a grid on an available rectangle
        given item size and gutter.
        Solves N*it_w + (N-1)*g <= av_w -> N <= floor((av_w+g)/(it_w+g))
        """
        if it_w <= 0 or it_h <= 0:
            return 0, 0, 0
        try:
            cols = int((av_w + g) / (it_w + g))
            rows = int((av_h + g) / (it_h + g))
        except Exception:
            cols, rows = 0, 0
        cols = max(cols, 0)
        rows = max(rows, 0)
        return cols * rows, cols, rows

    # Try normal orientation
    count1, cols1, rows1 = grid_count(avail_w, avail_h, eff_w, eff_h, gutter)
    best = {
        "count": int(count1),
        "cols": int(cols1),
        "rows": int(rows1),
        "rotated": False,
        "effective_item_w_mm": eff_w,
        "effective_item_h_mm": eff_h,
    }

    # Try rotated orientation if allowed
    if allow_rotation:
        count2, cols2, rows2 = grid_count(avail_w, avail_h, eff_h, eff_w, gutter)
        if int(count2) > best["count"]:
            best = {
                "count": int(count2),
                "cols": int(cols2),
                "rows": int(rows2),
                "rotated": True,
                "effective_item_w_mm": eff_h,
                "effective_item_h_mm": eff_w,
            }

    # Attach meta
    best.update(
        {
            "available_w_mm": avail_w,
            "available_h_mm": avail_h,
            "sheet_w_mm": sw,
            "sheet_h_mm": sh,
            "bleed_mm": bleed,
            "gutter_mm": gutter,
            "margin_mm": margin,
        }
    )
    return best


def items_per_sheet(
    sheet_w_mm,
    sheet_h_mm,
    item_w_mm,
    item_h_mm,
    bleed_mm: float = 3,
    gutter_mm: float = 1,
    margin_mm: float = 1,
    allow_rotation: bool = True,
) -> int:
    """
    Compatibility wrapper that returns the number of items that fit on the sheet (integer).
    Defaults:
      - bleed_mm = 3
      - gutter_mm = 5
      - margin_mm = 10 (gripper reserve)
    """
    layout = items_layout(
        sheet_w_mm=sheet_w_mm,
        sheet_h_mm=sheet_h_mm,
        item_w_mm=item_w_mm,
        item_h_mm=item_h_mm,
        bleed_mm=bleed_mm,
        gutter_mm=gutter_mm,
        margin_mm=margin_mm,
        allow_rotation=allow_rotation,
    )
    return int(layout.get("count", 0))


def sheets_needed(quantity: int, items_per_sheet: int) -> int:
    """
    Return number of sheets required to print `quantity` items given `items_per_sheet`.
    If items_per_sheet <= 0, treat as one item per sheet (sensible fallback).
    """
    try:
        q = int(quantity)
    except Exception:
        q = 0
    try:
        ips = int(items_per_sheet)
    except Exception:
        ips = 0

    if q <= 0:
        return 0
    if ips <= 0:
        # item doesn't fit (or invalid): treat as one per sheet (safe fallback)
        return q
    return math.ceil(q / ips)


def _round_up_to_multiple(value: int, base: int) -> int:
    """Round integer `value` up to next multiple of `base` (base>0)."""
    if base <= 0:
        return value
    return ((value + base - 1) // base) * base


def booklet_imposition(
    total_pages: int,
    final_page_w_mm: float,
    final_page_h_mm: float,
    sheet_w_mm: float,
    sheet_h_mm: float,
    *,
    bleed_mm: float = 3,
    gutter_mm: float = 5,
    margin_mm: float = 10,
    duplex: bool = True,
    enforce_signature_multiple: int = 4,
    cover_separate: bool = True,
    cover_sheet_w_mm: Optional[float] = None,
    cover_sheet_h_mm: Optional[float] = None,
    cover_bleed_mm: Optional[float] = None,
    cover_gutter_mm: Optional[float] = None,
    cover_margin_mm: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Compute sheets needed for a saddle-stitched booklet.

    Parameters
    ----------
    total_pages : int
        Number of final pages in the book (e.g., 32).
    final_page_w_mm, final_page_h_mm : numeric
        Final page dimensions in mm (A4 -> 210x297).
    sheet_w_mm, sheet_h_mm : numeric
        Production sheet dimensions used for the inner run (e.g., A3 -> 297x420).
    bleed_mm, gutter_mm, margin_mm : numeric
        Defaults for inner run.
    duplex : bool
        Whether printing is duplex (both sides).
    enforce_signature_multiple : int
        Usually 4 for saddle stitch (folded signatures of 4 pages per sheet side).
    cover_separate : bool
        If True, the cover will be printed as a separate run (default True).
    cover_sheet_* : Optional numeric
        If provided, cover uses a different production sheet (width, height) and
        optionally different bleed/gutter/margin. If not provided, cover uses the
        same layout as the inner run.

    Returns
    -------
    dict with keys (typical):
      - pages_original: provided total_pages
      - pages_rounded: rounded up to signature multiple (e.g., 32)
      - pages_inner: pages printed as inner run (rounded minus cover pages if cover_separate)
      - cover_pages: pages reserved for the cover (usually 4 if cover_separate)
      - pages_per_physical_sheet: pages that one physical sheet provides (inner run)
      - cover_pages_per_physical_sheet: pages per physical sheet for cover (if computed)
      - inner_sheets: physical sheets required for inner run
      - cover_sheets: physical sheets required for cover run
      - total_physical_sheets: sum of inner + cover sheets
      - notes: textual notes / errors
    """
    result: Dict[str, Any] = {}
    orig = int(total_pages or 0)
    result["pages_original"] = orig

    # 1) round up to signature multiple (usually 4)
    rounded = _round_up_to_multiple(orig, enforce_signature_multiple)
    result["pages_rounded"] = rounded
    notes = []

    if rounded != orig:
        notes.append(f"Rounded pages {orig} → {rounded} to meet {enforce_signature_multiple}-page signature.")

    # 2) compute how many final pages fit on a single SIDE of the inner sheet
    items_side = items_per_sheet(
        sheet_w_mm=sheet_w_mm,
        sheet_h_mm=sheet_h_mm,
        item_w_mm=final_page_w_mm,
        item_h_mm=final_page_h_mm,
        bleed_mm=bleed_mm,
        gutter_mm=gutter_mm,
        margin_mm=margin_mm,
    )
    # pages per physical sheet accounts for duplex
    pages_per_physical = items_side * (2 if duplex else 1)
    result["pages_per_physical_sheet"] = pages_per_physical

    if pages_per_physical <= 0:
        result["inner_sheets"] = None
        result["cover_sheets"] = None
        result["total_physical_sheets"] = None
        notes.append("ERROR: Final page does not fit on inner production sheet with the given bleed/gutter/margins.")
        result["notes"] = "\n".join(notes)
        return result

    # 3) determine cover pages (if separate)
    cover_pages = 4 if cover_separate else 0
    inner_pages = rounded - cover_pages if cover_separate else rounded
    if inner_pages < 0:
        inner_pages = 0

    result["pages_inner"] = inner_pages
    result["cover_pages"] = cover_pages

    # 4) compute inner sheets
    inner_sheets = ceil(inner_pages / pages_per_physical) if inner_pages > 0 else 0
    result["inner_sheets"] = int(inner_sheets)

    # 5) compute cover sheets (maybe different layout)
    cover_pages_per_physical = None
    cover_sheets = 0
    if cover_separate and cover_pages > 0:
        if cover_sheet_w_mm and cover_sheet_h_mm:
            cb_bleed = cover_bleed_mm if cover_bleed_mm is not None else bleed_mm
            cb_gutter = cover_gutter_mm if cover_gutter_mm is not None else gutter_mm
            cb_margin = cover_margin_mm if cover_margin_mm is not None else margin_mm
            cover_items_side = items_per_sheet(
                sheet_w_mm=cover_sheet_w_mm,
                sheet_h_mm=cover_sheet_h_mm,
                item_w_mm=final_page_w_mm,
                item_h_mm=final_page_h_mm,
                bleed_mm=cb_bleed,
                gutter_mm=cb_gutter,
                margin_mm=cb_margin,
            )
            cover_pages_per_physical = cover_items_side * (2 if duplex else 1)
        else:
            cover_pages_per_physical = pages_per_physical

        result["cover_pages_per_physical_sheet"] = cover_pages_per_physical

        if not cover_pages_per_physical or cover_pages_per_physical <= 0:
            notes.append("ERROR: Cover pages do not fit on cover production sheet/layout.")
            cover_sheets = None
        else:
            cover_sheets = ceil(cover_pages / cover_pages_per_physical)

    result["cover_sheets"] = int(cover_sheets or 0)
    result["total_physical_sheets"] = int((result["inner_sheets"] or 0) + (result["cover_sheets"] or 0))

    if notes:
        result["notes"] = "\n".join(notes)
    else:
        result["notes"] = ""

    return result
