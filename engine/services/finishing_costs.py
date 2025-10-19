from decimal import Decimal
from pricing.models import TieredFinishingPrice
from machines.models import FinishingService

def compute_finishing_cost(service: FinishingService, quantity: int) -> dict:
    """
    Calculate finishing cost for a service based on pricing method and calculation method.
    Returns a dict with total and formatted cost.
    """
    if not service:
        return {"total": Decimal("0.00"), "formatted": "KES 0.00"}

    unit_price = Decimal("0.00")

    # -------------------------------
    # 1. Resolve unit price
    # -------------------------------
    if service.pricing_method == FinishingService.PricingMethod.SIMPLE:
        unit_price = service.simple_price or Decimal("0.00")

    elif service.pricing_method == FinishingService.PricingMethod.TIERED:
        tier = (
            TieredFinishingPrice.objects
            .filter(service=service, min_quantity__lte=quantity, max_quantity__gte=quantity)
            .first()
        )
        if tier:
            unit_price = tier.price

    # -------------------------------
    # 2. Total cost
    # -------------------------------
    total_cost = Decimal(quantity) * unit_price

    # Enforce minimum charge
    if total_cost < (service.minimum_charge or Decimal("0.00")):
        total_cost = service.minimum_charge

    return {
        "total": total_cost,
        "formatted": f"{service.currency} {total_cost:,.2f}",
        "unit_price": unit_price,
    }
