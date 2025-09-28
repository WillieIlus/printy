# orders/services.py

from .models import Order, JobDeliverable
from products.models import ProductTemplate
from accounts.models import User

def create_deliverable_from_template(user: User, template: ProductTemplate) -> JobDeliverable:
    """
    Creates a new Order (if needed) and a new JobDeliverable pre-populated 
    with default values from a ProductTemplate.
    
    This is the "hook" part of the "hook and tweak" workflow.
    """
    # Find or create an Order for the user that is still a "cart"
    order, created = Order.objects.get_or_create(
        client=user,
        printer=template.company, # The product's company is the printer [cite: 68]
        status=Order.Status.PENDING_QUOTE
    )

    # Create a new deliverable linked to this order and the source template
    # We use the template's properties as defaults
    deliverable = JobDeliverable.objects.create(
        order=order,
        source_template=template,
        name=template.name, # e.g., "A4 Booklet" [cite: 69]
        quantity=template.minimum_order_quantity, # e.g., 100 [cite: 70]
        size=template.size, # The fixed size from the template [cite: 69]
        # You can set other defaults, like the cheapest paper option
        # cover_material = template.cover_range_gsm.order_by('...').first(),
    )
    
    return deliverable