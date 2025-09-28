# engine/services/products.py
from decimal import Decimal
import math

from engine.services import impositions, costs
from machines.models import MachineType      # This was correct
from pricing.models import DigitalPrintPrice   # This is the fix
from django.db.models import Max, Min



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
    

def get_product_price_range(template: "ProductTemplate") -> tuple[Decimal | None, Decimal | None]:
    """
    Calculates the lowest and highest possible price for a ProductTemplate
    based on its minimum quantity and available options.
    """
    qty = template.minimum_order_quantity
    materials = list(template.cover_range_gsm.all()) + list(template.insert_range_gsm.all())
    
    if not materials or not template.size:
        return (None, None)

    min_total = None
    max_total = None

    # Find all digital machines for the company
    machines = template.company.machines.filter(machine_type=MachineType.DIGITAL)

    for machine in machines:
        # Find all price rules for this machine and the allowed materials
        price_rules = DigitalPrintPrice.objects.filter(
            machine=machine,
            paper_type__in=materials
        )

        for rule in price_rules:
            items_per_sheet = impositions.items_per_sheet(
                # Note: You need to add sheet dimensions to your PaperType model
                # For now, let's assume a standard size like SRA3 (450x320)
                sheet_w_mm=450, 
                sheet_h_mm=320,
                item_w_mm=template.size.width_mm,
                item_h_mm=template.size.height_mm,
            )

            if not items_per_sheet:
                continue

            sheets_needed = impositions.sheets_needed(qty, items_per_sheet)
            
            # --- Calculate Minimum Path ---
            min_side_price = min(rule.single_side_price, rule.double_side_price)
            min_base_cost = Decimal(sheets_needed) * min_side_price
            min_finish_cost = sum(
                costs.calculate_finish_cost(finish, qty, sheets_needed)
                for finish in template.get_mandatory_finishings()
            )
            current_min = max(min_base_cost + min_finish_cost, rule.minimum_charge)
            
            if min_total is None or current_min < min_total:
                min_total = current_min

            # --- Calculate Maximum Path ---
            max_side_price = max(rule.single_side_price, rule.double_side_price)
            max_base_cost = Decimal(sheets_needed) * max_side_price
            # Max cost includes all mandatory AND optional finishings
            all_finishings = list(template.get_mandatory_finishings()) + list(template.get_optional_finishings())
            max_finish_cost = sum(
                costs.calculate_finish_cost(finish, qty, sheets_needed)
                for finish in all_finishings
            )
            current_max = max(max_base_cost + max_finish_cost, rule.minimum_charge)

            if max_total is None or current_max > max_total:
                max_total = current_max
                
    return (min_total, max_total)