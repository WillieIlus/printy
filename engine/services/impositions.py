# engine/services/impositions.py
"""
Sheet imposition calculations.
Responsible for figuring out how many final items fit onto a parent sheet,
given real-world print constraints (bleed, gutter, gripper margin).
"""

import math
from typing import Tuple


def items_per_sheet(
    sheet_w_mm: float,
    sheet_h_mm: float,
    item_w_mm: float,
    item_h_mm: float,
    bleed_mm: int = 3,
    gutter_mm: int = 5,
    gripper_mm: int = 10,
) -> int:
    """
    Calculate maximum number of items that fit on a sheet (portrait or landscape).

    Args:
        sheet_w_mm: Sheet width in millimeters.
        sheet_h_mm: Sheet height in millimeters.
        item_w_mm: Final trimmed item width.
        item_h_mm: Final trimmed item height.
        bleed_mm: Extra margin around artwork.
        gutter_mm: Gap between items on sheet.
        gripper_mm: Margin reserved for machine gripper (non-printable area).

    Returns:
        Maximum items that can fit on one sheet (portrait vs. landscape).
    """
    if not all([sheet_w_mm, sheet_h_mm, item_w_mm, item_h_mm]):
        return 0

    # Account for bleed
    artwork_w = item_w_mm + (2 * bleed_mm)
    artwork_h = item_h_mm + (2 * bleed_mm)

    # Reduce printable height by gripper
    usable_h = sheet_h_mm - gripper_mm
    if usable_h <= 0:
        return 0

    # Portrait orientation
    across_p = (sheet_w_mm + gutter_mm) // (artwork_w + gutter_mm)
    down_p   = (usable_h  + gutter_mm) // (artwork_h + gutter_mm)
    total_portrait = int(across_p * down_p)

    # Landscape orientation (swap width/height of artwork)
    across_l = (sheet_w_mm + gutter_mm) // (artwork_h + gutter_mm)
    down_l   = (usable_h  + gutter_mm) // (artwork_w + gutter_mm)
    total_landscape = int(across_l * down_l)

    return max(total_portrait, total_landscape)


def sheets_needed(quantity: int, items_per_sheet: int) -> int:
    """
    Given a quantity and items per sheet, calculate how many sheets are needed.
    Uses ceiling division.

    Args:
        quantity: Total number of finished items needed.
        items_per_sheet: How many fit on one sheet.

    Returns:
        Total sheets required.
    """
    if items_per_sheet <= 0:
        return 0
    return math.ceil(quantity / items_per_sheet)


def best_fit_orientation(
    sheet_w_mm: float,
    sheet_h_mm: float,
    item_w_mm: float,
    item_h_mm: float,
    bleed_mm: int = 3,
    gutter_mm: int = 5,
    gripper_mm: int = 10,
) -> Tuple[str, int]:
    """
    Determine whether portrait or landscape imposition yields more items.

    Returns:
        (orientation, items_per_sheet)
        orientation: 'portrait' or 'landscape'
        items_per_sheet: how many items fit in that orientation
    """
    if not all([sheet_w_mm, sheet_h_mm, item_w_mm, item_h_mm]):
        return ("none", 0)

    # Account for bleed
    artwork_w = item_w_mm + (2 * bleed_mm)
    artwork_h = item_h_mm + (2 * bleed_mm)

    usable_h = sheet_h_mm - gripper_mm
    if usable_h <= 0:
        return ("none", 0)

    across_p = (sheet_w_mm + gutter_mm) // (artwork_w + gutter_mm)
    down_p   = (usable_h  + gutter_mm) // (artwork_h + gutter_mm)
    total_portrait = int(across_p * down_p)

    across_l = (sheet_w_mm + gutter_mm) // (artwork_h + gutter_mm)
    down_l   = (usable_h  + gutter_mm) // (artwork_w + gutter_mm)
    total_landscape = int(across_l * down_l)

    if total_portrait >= total_landscape:
        return ("portrait", total_portrait)
    return ("landscape", total_landscape)
