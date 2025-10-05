# engine/services/costs.py 
from decimal import Decimal
from typing import Optional
from pricing.models import DigitalPrintPrice, FinishingService


# ---------------- Digital Print Costs ----------------
import logging
logger = logging.getLogger(__name__)

def _calculate_flat_price(self):
    if not self.inner_material or not self.inner_machine:
        return Decimal("0.00")

    logger.debug(f"Material: {self.inner_material}, Size: {self.size}, Machine: {self.inner_machine}")
    logger.debug(f"Inner material dims: {getattr(self.inner_material, 'width_mm', None)} x {getattr(self.inner_material, 'height_mm', None)}")

    items_ps = impositions.items_per_sheet(
        sheet_w_mm=self.inner_material.width_mm,
        sheet_h_mm=self.inner_material.height_mm,
        item_w_mm=self.size.width_mm,
        item_h_mm=self.size.height_mm,
        bleed_mm=self.bleed_mm,
        gutter_mm=self.gutter_mm
    )
    sheets = impositions.sheets_needed(self.quantity, items_ps)
    return costs.digital_section_cost(self.inner_machine, self.inner_material, self.inner_sidedness, sheets)


def digital_section_cost(machine, material, sidedness: str, sheets_needed: int) -> Decimal:
    """
    Cost for one digital section (cover OR inners).
    Looks up DigitalPrintPrice for the given machine + material.
    """
    if not machine or not material or sheets_needed <= 0:
        return Decimal("0.00")

    try:
        rule: DigitalPrintPrice = DigitalPrintPrice.objects.get(
            machine=machine, paper_type=material
        )
    except DigitalPrintPrice.DoesNotExist:
        return Decimal("0.00")

    if sidedness == "S2":  # double-sided
        per_sheet = rule.double_side_price or Decimal("0.00")
    else:
        per_sheet = rule.single_side_price or Decimal("0.00")

    subtotal = Decimal(sheets_needed) * per_sheet
    minimum = rule.minimum_charge or Decimal("0.00")

    return max(subtotal, minimum)


# ---------------- Finishing Costs ----------------

def finishing_cost(service: FinishingService, units: int, sheets: Optional[int] = None) -> Decimal:
    """
    Calculate finishing cost for a single FinishingService.
    Applies calculation_method and minimum_charge.
    """
    if not service:
        return Decimal("0.00")

    price = service.simple_price or Decimal("0.00")
    min_charge = service.minimum_charge or Decimal("0.00")

    if service.calculation_method == FinishingService.CalculationMethod.PER_ITEM:
        sub = Decimal(units) * price
    elif service.calculation_method == FinishingService.CalculationMethod.PER_SHEET_SINGLE_SIDED:
        sub = Decimal(sheets or 0) * price
    elif service.calculation_method == FinishingService.CalculationMethod.PER_SQ_METER:
        # Not usually applied to digital, but supported
        sub = Decimal(units) * price
    else:
        sub = Decimal("0.00")

    return max(sub, min_charge)


def finishing_total(finishing_links, applies_to: str, units: int, cover_sheets: int, inner_sheets: int) -> Decimal:
    """
    Sum finishing costs for a deliverable's finishing set.
    finishing_links = queryset of DeliverableFinishing
    applies_to = "cover", "inner", or "book"
    """
    total = Decimal("0.00")

    for link in finishing_links.select_related("service").all():
        if link.applies_to != applies_to:
            continue

        service = link.service
        if applies_to == "cover":
            total += finishing_cost(service, units, sheets=cover_sheets)
        elif applies_to == "inner":
            total += finishing_cost(service, units, sheets=inner_sheets)
        elif applies_to == "book":
            total += finishing_cost(service, units)
    return total


# ---------------- Deliverable Total ----------------

def deliverable_total(
    deliverable,
    cover_sheets: int,
    inner_sheets: int,
) -> Decimal:
    """
    Compute the total cost of a deliverable:
    - Cover cost
    - Inner cost
    - Finishing (cover + inner + book)
    """
    # Cover cost
    cover_cost = digital_section_cost(
        deliverable.cover_machine,
        deliverable.cover_material,
        deliverable.cover_sidedness,
        cover_sheets,
    )

    # Inner cost
    inner_cost = digital_section_cost(
        deliverable.inner_machine,
        deliverable.inner_material,
        deliverable.inner_sidedness,
        inner_sheets,
    )

    # Finishing
    cover_fin = finishing_total(deliverable.deliverablefinishing_set, "cover", deliverable.quantity, cover_sheets, inner_sheets)
    inner_fin = finishing_total(deliverable.deliverablefinishing_set, "inner", deliverable.quantity, cover_sheets, inner_sheets)
    book_fin  = finishing_total(deliverable.deliverablefinishing_set, "book",  deliverable.quantity, cover_sheets, inner_sheets)

    total = cover_cost + inner_cost + cover_fin + inner_fin + book_fin
    return total.quantize(Decimal("0.01"))
