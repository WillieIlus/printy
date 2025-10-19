# inside deliverable_summary()

# 🪄 Finishing cost calculation
finishing_total = Decimal("0.00")
finishing_lines = ""

if hasattr(deliverable, "deliverablefinishing_set"):
    finishing_links = deliverable.deliverablefinishing_set.all()
else:
    finishing_links = deliverable.finishings.all()

# Calculate job data
from engine.services.impositions import get_job_sheets_needed
sheet_count = get_job_sheets_needed(deliverable)
side_count = 2 if str(getattr(deliverable, "sidedness", "single")).lower() in ["double", "s2", "duplex"] else 1

job_data = {
    "sheet_count": sheet_count,
    "copy_count": getattr(deliverable, "quantity", 0),
    "set_count": getattr(deliverable, "quantity", 0),  # can adjust for booklets later
    "side_count": side_count,
}

for link in finishing_links:
    if hasattr(link, "service"):
        service = link.service
        machine = link.machine
        qty_override = getattr(link, "quantity_override", None)
    else:
        service = link
        machine = deliverable.machine
        qty_override = None

    # if qty_override is provided, override calculation
    if qty_override:
        job_data_override = job_data.copy()
        # Force quantity based on the calculation method
        if service.calculation_method == FinishingService.CalculationMethod.PER_JOB:
            job_data_override["sheet_count"] = 1
            job_data_override["copy_count"] = 1
            job_data_override["set_count"] = 1
        else:
            job_data_override["sheet_count"] = qty_override
            job_data_override["copy_count"] = qty_override
            job_data_override["set_count"] = qty_override
        fc = compute_finishing_cost(service, machine, job_data_override)
    else:
        fc = compute_finishing_cost(service, machine, job_data)

    finishing_total += fc["total"]
    finishing_lines += (
        f"✨ {service.name} on {machine.name}: "
        f"{fc['quantity']} × {fc['unit_price']} = {fc['formatted']}\n"
    )

if finishing_lines:
    base_msg += finishing_lines

# 💰 Grand total
grand_total = print_cost + finishing_total
base_msg += f"💵 Grand Total: KES {grand_total:,.2f}\n"
