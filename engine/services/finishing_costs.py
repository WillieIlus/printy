# services/finishing_costs.py
from decimal import Decimal
from pricing.models import TieredFinishingPrice
from machines.models import FinishingService

def compute_finishing_cost(service: FinishingService, machine, job_data: dict) -> dict:
    """
    Calculate finishing cost for a given service, machine, and job.
    job_data should contain:
        - copy_count
        - set_count
        - sheet_count
        - side_count
    """
    if not service or not machine:
        return {"total": Decimal("0.00"), "formatted": "KES 0.00", "unit_price": Decimal("0.00")}

    # Determine quantity based on calculation method
    method = service.calculation_method
    qty = 0

    if method == FinishingService.CalculationMethod.PER_JOB:
        qty = 1
    elif method == FinishingService.CalculationMethod.PER_SET:
        qty = job_data.get("set_count", 0) or 0
    elif method == FinishingService.CalculationMethod.PER_COPY:
        qty = job_data.get("copy_count", 0) or 0
    elif method == FinishingService.CalculationMethod.PER_SHEET:
        qty = job_data.get("sheet_count", 0) or 0
    elif method == FinishingService.CalculationMethod.PER_SHEET_PER_SIDE:
        qty = job_data.get("sheet_count", 0) * job_data.get("side_count", 1)

    # Find tiered pricing for that machine and service
    tier = (
        TieredFinishingPrice.objects
        .filter(service=service, machine=machine, min_quantity__lte=qty, max_quantity__gte=qty)
        .first()
    )

    unit_price = tier.price if tier else Decimal("0.00")
    total_cost = Decimal(qty) * unit_price

    return {
        "total": total_cost,
        "formatted": f"{tier.currency if tier else 'KES'} {total_cost:,.2f}",
        "unit_price": unit_price,
        "quantity": qty
    }
