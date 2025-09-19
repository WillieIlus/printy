# engine/services/products.py
from decimal import Decimal
import maths

from engine.services import impositions, costs
from machines.models import MachineType, DigitalPrintPrice


def product_starting_price(template) -> Decimal | None:
    """
    Calculate the lowest possible starting price for a given ProductTemplate.

    It uses:
      - Minimum order quantity from the template
      - Allowed paper materials (cover + insert ranges)
      - Digital machine pricing rules
      - Mandatory finishing services
    """

    qty = template.minimum_order_quantity
    lowest_total = None

    # Collect all available paper materials (cover + insert ranges)
    materials = list(template.cover_range_gsm.all()) + list(template.insert_range_gsm.all())

    if not materials or not template.size:
        return None  # Cannot price without paper or size

    # Iterate over each material option
    for material in materials:
        # Find all digital machines for this company
        machines = template.company.machines.filter(machine_type=MachineType.DIGITAL)

        for machine in machines:
            # Find a matching price rule for this paper
            price_rule = DigitalPrintPrice.objects.filter(
                machine=machine,
                paper_type=material
            ).first()

            if not price_rule:
                continue

            # Calculate imposition (items per sheet)
            items_per_sheet = impositions.items_per_sheet(
                sheet_w_mm=material.default_sheet_width_mm,
                sheet_h_mm=material.default_sheet_height_mm,
                item_w_mm=template.size.width_mm,
                item_h_mm=template.size.height_mm,
            )
            if not items_per_sheet:
                continue

            sheets_needed = impositions.sheets_needed(qty, items_per_sheet)

            # Try both single- and double-sided costs
            for side_price in [price_rule.single_side_price, price_rule.double_side_price]:
                if not side_price:
                    continue

                base_cost = Decimal(sheets_needed) * side_price

                # Add mandatory finishings
                finishing_total = sum(
                    costs.calculate_finish_cost(finish, qty, sheets_needed)
                    for finish in template.mandatory_finishings.all()
                )

                total = base_cost + finishing_total
                total = max(total, price_rule.minimum_charge or Decimal("0.00"))

                if lowest_total is None or total < lowest_total:
                    lowest_total = total

    return lowest_total
    
    
    
    