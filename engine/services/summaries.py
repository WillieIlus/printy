# engine/services/summaries.py
from decimal import Decimal
from typing import Optional
from engine.services.impositions import items_per_sheet, get_job_sheets_needed
from engine.services.costs import compute_total_cost
from engine.services.finishing_costs import compute_finishing_cost
from machines.models import Machine


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
    price_obj = getattr(deliverable, "print_price", None)
    if price_obj is not None and getattr(price_obj, "size", None) is not None:
        return price_obj.size, "price.size"

    sra3 = _find_sra3()
    if sra3:
        return sra3, "SRA3"

    machine = getattr(deliverable, "machine", None)
    if machine and hasattr(machine, "supported_sizes"):
        try:
            first_supported = machine.supported_sizes.first()
        except Exception:
            first_supported = None
        if first_supported:
            return first_supported, "machine.supported_size"

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
    Human-readable production summary and cost snippet for a job deliverable.
    Combines print cost + finishing cost to get the grand total.
    """

    name = getattr(deliverable, "name", "Deliverable")
    qty = getattr(deliverable, "quantity", 0)
    final_size = getattr(deliverable, "size", None)
    final_w = getattr(final_size, "width_mm", None) if final_size else None
    final_h = getattr(final_size, "height_mm", None) if final_size else None

    bleed = getattr(deliverable, "bleed_mm", 3)
    gutter = getattr(deliverable, "gutter_mm", 5)

    # 🧾 Resolve production sheet
    sheet, source = _resolve_sheet_for_deliverable(deliverable)
    if sheet is None:
        return f"{name}: Could not resolve a production sheet size. Quantity: {qty}."

    per_sheet = items_per_sheet(
        sheet_w_mm=getattr(sheet, "width_mm", 0),
        sheet_h_mm=getattr(sheet, "height_mm", 0),
        item_w_mm=final_w or 0,
        item_h_mm=final_h or 0,
        bleed_mm=bleed,
        gutter_mm=gutter,
    )

    import math
    sheets = math.ceil(qty / int(per_sheet)) if per_sheet else 0

    machine = getattr(deliverable, "machine", None)
    paper = getattr(deliverable, "material", None)
    sides = getattr(deliverable, "sides", "??")
    machine_name = getattr(machine, "name", "None")
    paper_name = getattr(paper, "name", "None")
    sheet_name = getattr(sheet, "name", "Unknown")

    base_msg = (
        f"📄 {name}: {int(per_sheet)} pcs fit per {sheet_name} "
        f"({sheet.width_mm}×{sheet.height_mm} mm)\n"
        f"🧮 For {qty} pcs → {sheets} sheet(s). (sheet source: {source})\n"
        f"🖨 Machine: {machine_name}\n"
        f"📏 Paper type: {paper_name}\n"
        f"↔️ sides: {sides}\n"
    )

    # 🖨 Print cost
    print_cost_data = compute_total_cost(deliverable)
    print_cost = print_cost_data.get("total_cost", Decimal("0.00"))
    print_cost_fmt = print_cost_data.get("total_cost_formatted", "KES 0.00")
    base_msg += f"🧾 Print Cost: {print_cost_fmt}\n"

    # 🪄 Finishing cost calculation
    finishing_total = Decimal("0.00")
    finishing_lines = ""

    # Through table support
    if hasattr(deliverable, "deliverablefinishing_set"):
        finishing_links = deliverable.deliverablefinishing_set.all()
    else:
        finishing_links = deliverable.finishings.all()

    # Job data for calculation
    sheet_count = sheets
    side_count = 2 if str(sides).lower() in ["double", "s2", "duplex"] else 1

    job_data = {
        "sheet_count": sheet_count,
        "copy_count": qty,
        "set_count": qty,
        "side_count": side_count,
    }

    for link in finishing_links:
        if hasattr(link, "service"):
            service = link.service
            machine_used = link.machine
            qty_override = getattr(link, "quantity_override", None)
        else:
            service = link
            machine_used = machine
            qty_override = None

        # Optional override
        if qty_override:
            custom_data = job_data.copy()
            custom_data["sheet_count"] = qty_override
            custom_data["copy_count"] = qty_override
            custom_data["set_count"] = qty_override
            fc = compute_finishing_cost(service, machine_used, custom_data)
        else:
            fc = compute_finishing_cost(service, machine_used, job_data)

        finishing_total += fc["total"]
        finishing_lines += (
            f"✨ {service.name} on {machine_used.name}: "
            f"{fc['quantity']} × {fc['unit_price']} = {fc['formatted']}\n"
        )

    if finishing_lines:
        base_msg += finishing_lines

    # 💰 Grand total
    grand_total = print_cost + finishing_total
    base_msg += f"💵 Grand Total: KES {grand_total:,.2f}\n"

    return base_msg.strip()
