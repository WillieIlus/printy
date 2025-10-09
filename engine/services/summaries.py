"""
engine/services/summaries.py

Production summary + short cost snippet using the direct-price cost service.
Does NOT use the product service.
"""
from typing import Optional

from papers.models import ProductionPaperSize
from engine.services.impositions import items_per_sheet


def _find_sra3() -> Optional[ProductionPaperSize]:
    qs = ProductionPaperSize.objects.filter(name__iexact="SRA3")
    if qs.exists():
        return qs.first()
    qs = ProductionPaperSize.objects.filter(name__icontains="sra")
    for p in qs:
        name_lower = (p.name or "").lower()
        if "3" in name_lower or "iii" in name_lower:
            return p
    return None


def _resolve_sheet_for_deliverable(deliverable):
    """
    Resolve a sheet-size object (provides width_mm, height_mm, name).
    Preference:
      1) deliverable.print_price.size
      2) SRA3
      3) deliverable.inner_machine.supported_sizes.first()
      4) deliverable.inner_material.size
    """
    price_obj = getattr(deliverable, "print_price", None)
    if price_obj is not None and getattr(price_obj, "size", None) is not None:
        return price_obj.size, "price.size"

    sra3 = _find_sra3()
    if sra3 is not None:
        return sra3, "SRA3"

    machine = getattr(deliverable, "inner_machine", None)
    if machine is not None and getattr(machine, "supported_sizes", None) is not None:
        try:
            first_supported = machine.supported_sizes.first()
        except Exception:
            first_supported = None
        if first_supported:
            return first_supported, "machine.supported_size"

    mat = getattr(deliverable, "inner_material", None)
    if mat is not None:
        try:
            mat_size = getattr(mat, "size", None)
        except Exception:
            mat_size = None
        if mat_size:
            return mat_size, "material.size"

    return None, "none"


def deliverable_summary(deliverable) -> str:
    """
    Human readable production summary and short cost snippet (direct-price only).
    """
    name = getattr(deliverable, "name", "Deliverable")
    qty = getattr(deliverable, "quantity", 0)

    final_size = getattr(deliverable, "size", None)
    final_w = getattr(final_size, "width_mm", None) if final_size else None
    final_h = getattr(final_size, "height_mm", None) if final_size else None

    bleed = getattr(deliverable, "bleed_mm", 3)
    gutter = getattr(deliverable, "gutter_mm", 5)
    gripper = getattr(deliverable, "gripper_mm", 10)

    sheet, source = _resolve_sheet_for_deliverable(deliverable)
    if sheet is None:
        return f"{name}: Could not resolve a production sheet size (no price.size, SRA3, machine or material size). Quantity: {qty}."

    # booklet?
    is_booklet = bool(getattr(deliverable, "saddle_stitched", False)) or bool(getattr(deliverable, "total_pages", None))
    if is_booklet:
        try:
            from engine.services.costs import compute_sheets_for_deliverable, compute_total_cost
        except Exception:
            return f"{name}: Booklet (cost/imposition services unavailable)."

        sheets_info = compute_sheets_for_deliverable(deliverable, price_obj=getattr(deliverable, "print_price", None))
        pages = int(getattr(deliverable, "total_pages", 0) or 0)
        inner = sheets_info.get("inner_sheets", 0) or 0
        cover = sheets_info.get("cover_sheets", 0) or 0
        total = sheets_info.get("total_physical_sheets", inner + cover)

        base_msg = f"{name}: {pages}pp saddle-stitched. Inner run: {inner} sheet(s). Cover run: {cover} sheet(s). Total physical sheets: {total} (sheet source: {source})."

        try:
            cost = compute_total_cost(deliverable, getattr(deliverable, "print_price", None))
            return base_msg + f" Estimated cost: {cost.get('total_cost_formatted', 'KES 0.00')}."
        except Exception:
            return base_msg

    # non-booklet
    items = items_per_sheet(
        sheet_w_mm=getattr(sheet, "width_mm", None),
        sheet_h_mm=getattr(sheet, "height_mm", None),
        item_w_mm=final_w,
        item_h_mm=final_h,
        bleed_mm=bleed,
        gutter_mm=gutter,
        margin_mm=gripper,
    )
    if not items or int(items) <= 0:
        return f"{name}: Item ({final_w}×{final_h} mm) does NOT fit on {sheet.name} ({sheet.width_mm}×{sheet.height_mm} mm) even after bleed."

    # sheets needed
    import math
    sheets = math.ceil(qty / int(items))

    base_msg = f"{name}: {int(items)} pcs fit per {sheet.name} ({sheet.width_mm}×{sheet.height_mm} mm) including bleed {bleed}mm and gutter {gutter}mm. For {qty} pcs → {sheets} sheet(s). (sheet source: {source})"

    # cost snippet
    try:
        from engine.services.costs import compute_total_cost
        cost = compute_total_cost(deliverable, getattr(deliverable, "print_price", None))
        return base_msg + f" Estimated cost: {cost.get('total_cost_formatted', 'KES 0.00')}."
    except Exception:
        return base_msg
