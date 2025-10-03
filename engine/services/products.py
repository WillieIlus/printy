# engine/services/products.py
from decimal import Decimal
import math

from engine.services import impositions, costs
from machines.models import MachineType
from pricing.models import DigitalPrintPrice
from django.db.models import Max, Min

def product_starting_price(template) -> Decimal | None:
    """
    Calculate the lowest possible starting price for a given ProductTemplate.
    """
    qty = template.minimum_order_quantity
    lowest_total = None
    materials = list(template.cover_range_gsm.all()) + list(template.insert_range_gsm.all())

    if not materials or not template.size:
        return None

    for material in materials:
        # Ensure the material has a default production size defined [cite: 23]
        if not material.size:
            continue

        machines = template.company.machines.filter(machine_type=MachineType.DIGITAL)
        for machine in machines:
            price_rule = DigitalPrintPrice.objects.filter(
                machine=machine, paper_type=material
            ).first()

            if not price_rule:
                continue

            # **UPDATED**: Using the new centralized imposition service
            items_per_sheet = impositions.items_per_sheet(
                sheet_w_mm=material.size.width_mm,
                sheet_h_mm=material.size.height_mm,
                item_w_mm=template.size.width_mm,
                item_h_mm=template.size.height_mm,
            )
            
            if not items_per_sheet:
                continue

            sheets_needed = impositions.sheets_needed(qty, items_per_sheet)

            for side_price in [price_rule.single_side_price, price_rule.double_side_price]:
                if not side_price:
                    continue

                base_cost = Decimal(sheets_needed) * side_price
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
    Calculates the lowest and highest possible price for a ProductTemplate.
    """
    qty = template.minimum_order_quantity
    materials = list(template.cover_range_gsm.all()) + list(template.insert_range_gsm.all())
    
    if not materials or not template.size:
        return (None, None)

    min_total = None
    max_total = None
    machines = template.company.machines.filter(machine_type=MachineType.DIGITAL)

    for machine in machines:
        price_rules = DigitalPrintPrice.objects.filter(
            machine=machine, paper_type__in=materials
        )

        for rule in price_rules:
            # Ensure the paper type has a default production size defined [cite: 23]
            if not rule.paper_type.size:
                continue

            # **UPDATED**: Using the new service and getting sheet size from the FK [cite: 23]
            items_per_sheet = impositions.items_per_sheet(
                sheet_w_mm=rule.paper_type.size.width_mm,
                sheet_h_mm=rule.paper_type.size.height_mm,
                item_w_mm=template.size.width_mm,
                item_h_mm=template.size.height_mm,
            )

            if not items_per_sheet:
                continue

            sheets_needed = impositions.sheets_needed(qty, items_per_sheet)
            
            # --- Calculate Minimum Path ---
            min_side_price = min(rule.single_side_price, rule.double_side_price) if rule.double_side_price else rule.single_side_price
            min_base_cost = Decimal(sheets_needed) * min_side_price
            min_finish_cost = sum(
                costs.calculate_finish_cost(finish, qty, sheets_needed)
                for finish in template.get_mandatory_finishings()
            )
            current_min = max(min_base_cost + min_finish_cost, rule.minimum_charge)
            
            if min_total is None or current_min < min_total:
                min_total = current_min

            # --- Calculate Maximum Path ---
            max_side_price = max(rule.single_side_price, rule.double_side_price) if rule.double_side_price else rule.single_side_price
            max_base_cost = Decimal(sheets_needed) * max_side_price
            all_finishings = list(template.get_mandatory_finishings()) + list(template.get_optional_finishings())
            max_finish_cost = sum(
                costs.calculate_finish_cost(finish, qty, sheets_needed)
                for finish in all_finishings
            )
            current_max = max(max_base_cost + max_finish_cost, rule.minimum_charge)

            if max_total is None or current_max > max_total:
                max_total = current_max
                
    return (min_total, max_total)