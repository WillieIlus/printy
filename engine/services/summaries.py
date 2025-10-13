"""
Production summary + short cost snippet using the direct-price cost service.
"""

from typing import Optional
from decimal import Decimal
from engine.services.impositions import items_per_sheet
from engine.services.costs import compute_total_cost


# -------------------------------------------------------------------
# FIND SRA3 OR ALTERNATIVE SHEET SIZE
# -------------------------------------------------------------------
def _find_sra3():
    """
    Attempt to find a ProductionPaperSize object for SRA3 or a close match.
    Lazy import to avoid circular imports.
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
    # 1) Price size
    price_obj = getattr(deliverable, "print_price", None)
    if price_obj is not None and getattr(price_obj, "size", None) is not None:
        return price_obj.size, "price.size"

    # 2) SRA3 fallback
    sra3 = _find_sra3()
    if sra3:
        return sra3, "SRA3"

    # 3) Machine supported sizes
    machine = getattr(deliverable, "machine", None)
    if machine and hasattr(machine, "supported_sizes"):
        try:
            first_supported = machine.supported_sizes.first()
        except Exception:
            first_supported = None
        if first_supported:
            return first_supported, "machine.supported_size"

    # 4) Material size
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
    Human-readable production summary and cost snippet.
    Example:
      "Business Cards: 12 pcs fit per SRA3 ... Estimated cost: KES 2,000.00."
    """

    name = getattr(deliverable, "name", "Deliverable")
    qty = getattr(deliverable, "quantity", 0)

    # --- final size
    final_size = getattr(deliverable, "size", None)
    final_w = getattr(final_size, "width_mm", None) if final_size else None
    final_h = getattr(final_size, "height_mm", None) if final_size else None

    # --- print params
    bleed = getattr(deliverable, "bleed_mm", 3)
    gutter = getattr(deliverable, "gutter_mm", 5)
    gripper = getattr(deliverable, "gripper_mm", 10)

    # --- resolve production sheet
    sheet, source = _resolve_sheet_for_deliverable(deliverable)
    if sheet is None:
        return f"{name}: Could not resolve a production sheet size (no price.size, SRA3, machine or material size). Quantity: {qty}."

    # --- Booklet handling
    if bool(getattr(deliverable, "is_booklet", False)):
        pages = int(getattr(deliverable, "page_count", 0) or 0)
        base_msg = f"📚 {name}: {pages}pp booklet (saddle/perfect)."
        try:
            cost = compute_total_cost(deliverable)
            return base_msg + f" Estimated cost: {cost.get('total_cost_formatted', 'KES 0.00')}."
        except Exception as e:
            return base_msg + f" (cost unavailable: {e})"

    # --- Flat job imposition
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

    machine = getattr(deliverable, "machine", None)
    paper = getattr(deliverable, "material", None)
    sidedness = getattr(deliverable, "sidedness", "??")
    machine_name = getattr(machine, "name", "None")
    paper_name = getattr(paper, "name", "None")
    sheet_name = getattr(sheet, "name", "Unknown")

    base_msg = (
        f"📄 {name}: {int(items)} pcs fit per {sheet_name} "
        f"({sheet.width_mm}×{sheet.height_mm} mm)\n"
        f"🧮 For {qty} pcs → {sheets} sheet(s). (sheet source: {source})\n"
        f"🖨 Machine: {machine_name}\n"
        f"📏 Paper type: {paper_name}\n"
        f"↔️ Sidedness: {sidedness}\n"
    )

    # --- Compute total cost
    try:
        cost = compute_total_cost(deliverable)
        total_cost_fmt = cost.get("total_cost_formatted", "KES 0.00")
        details = cost.get("details", "")
        base_msg += f"💰 Estimated cost: {total_cost_fmt}\n{details}\n"
    except Exception as e:
        base_msg += f"⚠️ Cost computation failed: {e}\n"

    return base_msg.strip()
