# engine/services/summaries.py 
from decimal import Decimal
from typing import List

from engine.services import impositions


def deliverable_summary(deliverable, cover_sheets: int, inner_sheets: int) -> str:
    """
    Generate a human-readable production summary for a deliverable.
    Handles both simple items and booklets.
    """
    lines: List[str] = []

    if not deliverable.is_booklet:
        # ----- SIMPLE PRINT -----
        final_w, final_h = deliverable._final_dims_mm()
        per_sheet = deliverable.items_per_sheet(
            deliverable.cover_material.sheet_width_mm,
            deliverable.cover_material.sheet_height_mm,
        )
        if per_sheet == 0:
            return f"{deliverable.name}: Cannot fit on selected sheet."

        sheets_needed = impositions.sheets_needed(deliverable.quantity, per_sheet)
        sided = "double-sided" if deliverable.cover_sidedness == "S2" else "single-sided"

        lines.append(
            f"{deliverable.name} – {deliverable.quantity} copies "
            f"on {deliverable.cover_material.name}, "
            f"{per_sheet}-up imposition → {sheets_needed} sheets, {sided}."
        )

    else:
        # ----- BOOKLET -----
        pages = deliverable.page_count
        if pages % 4 != 0:
            rounded = pages + (4 - pages % 4)
            page_note = f" (rounded to {rounded}pg for binding)"
            pages = rounded
        else:
            page_note = ""

        lines.append(f"{deliverable.name} – {deliverable.quantity} × {pages}-page booklet{page_note}")

        if cover_sheets:
            sided = "double-sided" if deliverable.cover_sidedness == "S2" else "single-sided"
            lines.append(
                f"- Cover: {cover_sheets} sheets of {deliverable.cover_material.name}, {sided}."
            )
        if inner_sheets:
            sided = "double-sided" if deliverable.inner_sidedness == "S2" else "single-sided"
            lines.append(
                f"- Inners: {inner_sheets} sheets of {deliverable.inner_material.name}, {sided}."
            )

    # ----- FINISHING -----
    finish_links = deliverable.deliverablefinishing_set.select_related("service").all()
    if finish_links.exists():
        lines.append("- Finishing:")
        for link in finish_links:
            lines.append(f"  • {link.service.name} ({link.applies_to})")

    return "\n".join(lines)
