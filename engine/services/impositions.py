# engine/services/impositions.py
import math
from typing import Dict, Any

def best_fit_orientation(
    sheet_w_mm: float,
    sheet_h_mm: float,
    item_w_mm: float,
    item_h_mm: float,
    bleed_mm: int = 3,
    gutter_mm: int = 5,
) -> Dict[str, Any]:
    """
    Calculates the best orientation (portrait or landscape) for imposing an item
    onto a sheet to maximize the number of items per sheet.

    Args:
        sheet_w_mm: Width of the production sheet in mm.
        sheet_h_mm: Height of the production sheet in mm.
        item_w_mm: Width of the final item in mm.
        item_h_mm: Height of the final item in mm.
        bleed_mm: Bleed margin in mm to add to each side of the item.
        gutter_mm: Gutter space in mm between items.

    Returns:
        A dictionary containing the best count, orientation, columns, and rows.
        Example: {'count': 10, 'orientation': 'portrait', 'cols': 2, 'rows': 5}
    """
    # Item dimensions including bleed
    item_w_bleed = item_w_mm + (2 * bleed_mm)
    item_h_bleed = item_h_mm + (2 * bleed_mm)

    if item_w_bleed <= 0 or item_h_bleed <= 0:
        return {'count': 0, 'orientation': 'none', 'cols': 0, 'rows': 0}

    # --- Calculate for Portrait orientation (item not rotated) ---
    # Effective space needed per item, including its share of the gutter
    eff_w_port = item_w_bleed + gutter_mm
    eff_h_port = item_h_bleed + gutter_mm
    
    # We add gutter_mm to sheet dimensions because the last item doesn't have a trailing gutter
    cols_port = math.floor((sheet_w_mm + gutter_mm) / eff_w_port)
    rows_port = math.floor((sheet_h_mm + gutter_mm) / eff_h_port)
    total_port = cols_port * rows_port

    # --- Calculate for Landscape orientation (item rotated) ---
    # Effective space needed per item, but with dimensions swapped
    eff_w_land = item_h_bleed + gutter_mm # item height is now width
    eff_h_land = item_w_bleed + gutter_mm # item width is now height
    
    cols_land = math.floor((sheet_w_mm + gutter_mm) / eff_w_land)
    rows_land = math.floor((sheet_h_mm + gutter_mm) / eff_h_land)
    total_land = cols_land * rows_land

    # --- Compare and return the best fit ---
    if total_port >= total_land:
        return {
            'count': total_port,
            'orientation': 'portrait',
            'cols': cols_port,
            'rows': rows_port,
        }
    else:
        return {
            'count': total_land,
            'orientation': 'landscape',
            'cols': cols_land,
            'rows': rows_land,
        }

def items_per_sheet(
    sheet_w_mm: float,
    sheet_h_mm: float,
    item_w_mm: float,
    item_h_mm: float,
    bleed_mm: int = 3,
    gutter_mm: int = 5,
) -> int:
    """Convenience wrapper around best_fit_orientation to get only the count."""
    fit_data = best_fit_orientation(
        sheet_w_mm, sheet_h_mm, item_w_mm, item_h_mm, bleed_mm, gutter_mm
    )
    return fit_data.get('count', 0)

def sheets_needed(quantity: int, items_per_sheet: int) -> int:
    """Calculates total production sheets needed for a given quantity."""
    if not items_per_sheet or items_per_sheet == 0:
        return 0  # Avoid division by zero
    return math.ceil(quantity / items_per_sheet)


# # engine/services/impositions.py
# """
# Sheet imposition calculations.
# Responsible for figuring out how many final items fit onto a parent sheet,
# given real-world print constraints (bleed, gutter, gripper margin).
# """

# import math
# from typing import Tuple


# def items_per_sheet(
#     sheet_w_mm: float,
#     sheet_h_mm: float,
#     item_w_mm: float,
#     item_h_mm: float,
#     bleed_mm: int = 3,
#     gutter_mm: int = 5,
#     gripper_mm: int = 10,
# ) -> int:
#     """
#     Calculate maximum number of items that fit on a sheet (portrait or landscape).

#     Args:
#         sheet_w_mm: Sheet width in millimeters.
#         sheet_h_mm: Sheet height in millimeters.
#         item_w_mm: Final trimmed item width.
#         item_h_mm: Final trimmed item height.
#         bleed_mm: Extra margin around artwork.
#         gutter_mm: Gap between items on sheet.
#         gripper_mm: Margin reserved for machine gripper (non-printable area).

#     Returns:
#         Maximum items that can fit on one sheet (portrait vs. landscape).
#     """
#     if not all([sheet_w_mm, sheet_h_mm, item_w_mm, item_h_mm]):
#         return 0

#     # Account for bleed
#     artwork_w = item_w_mm + (2 * bleed_mm)
#     artwork_h = item_h_mm + (2 * bleed_mm)

#     # Reduce printable height by gripper
#     usable_h = sheet_h_mm - gripper_mm
#     if usable_h <= 0:
#         return 0

#     # Portrait orientation
#     across_p = (sheet_w_mm + gutter_mm) // (artwork_w + gutter_mm)
#     down_p   = (usable_h  + gutter_mm) // (artwork_h + gutter_mm)
#     total_portrait = int(across_p * down_p)

#     # Landscape orientation (swap width/height of artwork)
#     across_l = (sheet_w_mm + gutter_mm) // (artwork_h + gutter_mm)
#     down_l   = (usable_h  + gutter_mm) // (artwork_w + gutter_mm)
#     total_landscape = int(across_l * down_l)

#     return max(total_portrait, total_landscape)


# def sheets_needed(quantity: int, items_per_sheet: int) -> int:
#     """
#     Given a quantity and items per sheet, calculate how many sheets are needed.
#     Uses ceiling division.

#     Args:
#         quantity: Total number of finished items needed.
#         items_per_sheet: How many fit on one sheet.

#     Returns:
#         Total sheets required.
#     """
#     if items_per_sheet <= 0:
#         return 0
#     return math.ceil(quantity / items_per_sheet)


# def best_fit_orientation(
#     sheet_w_mm: float,
#     sheet_h_mm: float,
#     item_w_mm: float,
#     item_h_mm: float,
#     bleed_mm: int = 3,
#     gutter_mm: int = 5,
#     gripper_mm: int = 10,
# ) -> Tuple[str, int]:
#     """
#     Determine whether portrait or landscape imposition yields more items.

#     Returns:
#         (orientation, items_per_sheet)
#         orientation: 'portrait' or 'landscape'
#         items_per_sheet: how many items fit in that orientation
#     """
#     if not all([sheet_w_mm, sheet_h_mm, item_w_mm, item_h_mm]):
#         return ("none", 0)

#     # Account for bleed
#     artwork_w = item_w_mm + (2 * bleed_mm)
#     artwork_h = item_h_mm + (2 * bleed_mm)

#     usable_h = sheet_h_mm - gripper_mm
#     if usable_h <= 0:
#         return ("none", 0)

#     across_p = (sheet_w_mm + gutter_mm) // (artwork_w + gutter_mm)
#     down_p   = (usable_h  + gutter_mm) // (artwork_h + gutter_mm)
#     total_portrait = int(across_p * down_p)

#     across_l = (sheet_w_mm + gutter_mm) // (artwork_h + gutter_mm)
#     down_l   = (usable_h  + gutter_mm) // (artwork_w + gutter_mm)
#     total_landscape = int(across_l * down_l)

#     if total_portrait >= total_landscape:
#         return ("portrait", total_portrait)
#     return ("landscape", total_landscape)
