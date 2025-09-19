
# pricing/base_item.py
"""I wonder how this BaseItem has fields, are they necessary? Most important part is calculate imposition for things like business cards which will be imposed on an A3 \
the default size of most digital machine, then there will be need to cut(a finishing service) to get the final size(client facing size)
Booklet are important also as an a4 booklet duplex with have 4 pages in one sheet printed both sides"""

from decimal import Decimal

class BaseItem(models.Model):
    """Abstract model for all items that can be part of a Job."""
    machine = models.ForeignKey(Machine, on_delete=models.PROTECT, null=True, blank=True)
    quantity = models.PositiveIntegerField(default=1, help_text=_("Number of units for this specific item."))
    finishing_options = models.ManyToManyField(FinishingService, blank=True, help_text=_("Additional finishing services for this item."))

    class Meta:
        abstract = True

    def _calculate_imposition(self, sheet_w, sheet_h, item_w, item_h, bleed=3, gutter=5, gripper=10):
        """
        Calculates the number of items that can fit on a sheet, accounting for
        real-world printing constraints.
        """
        if item_w == 0 or item_h == 0:
            return 0
        artwork_w = item_w + (2 * bleed)
        artwork_h = item_h + (2 * bleed)
        usable_sheet_h = sheet_h - gripper
        
        items_across_p = (sheet_w + gutter) // (artwork_w + gutter)
        items_down_p = (usable_sheet_h + gutter) // (artwork_h + gutter)
        total_portrait = items_across_p * items_down_p

        items_across_l = (sheet_w + gutter) // (artwork_h + gutter)
        items_down_l = (usable_sheet_h + gutter) // (artwork_w + gutter)
        total_landscape = items_across_l * items_down_l

        return max(total_portrait, total_landscape)
    
class BasePricingItem:
    """
    Abstract class for a single component of a job
    (cover, inside pages, posters, stickers, etc.)
    """

    def __init__(self, quantity, material=None, machine=None, finishes=None):
        self.quantity = quantity
        self.material = material
        self.machine = machine
        self.finishes = finishes or []

    def calculate_cost(self):
        """
        Must be implemented by subclasses for their specific process.
        Should always return a Decimal.
        """
        raise NotImplementedError("Subclasses must implement calculate_cost()")

    def calculate_finishing_cost(self):
        """
        Shared logic: sum of all finishing service costs.
        """
        total = Decimal("0.00")
        for finish in self.finishes:
            total += finish.calculate_cost(self.quantity)
        return total


# pricing/digital_item.py
from decimal import Decimal
from pricing.base_item import BasePricingItem

class DigitalPricingItem(BasePricingItem):
    def calculate_cost(self):
        if not self.material or not self.machine:
            return Decimal("0.00")

        # Fetch matching price rule (digital press + material)
        price_rule = self.machine.digitalpressprice_set.filter(material=self.material).first()
        if not price_rule:
            return Decimal("0.00")

        # Assume imposition is precomputed on machine
        items_per_sheet = self.machine.company.calculate_imposition(
            sheet_width=self.material.sheet_width_mm,
            sheet_height=self.material.sheet_height_mm,
            final_width=self.material.final_size.width_mm,
            final_height=self.material.final_size.height_mm,
        )
        if not items_per_sheet:
            return Decimal("0.00")

        sheets_needed = -(-self.quantity // items_per_sheet)  # ceil division
        base_cost = sheets_needed * price_rule.price_single_sided

        # Add finishing costs
        return base_cost + self.calculate_finishing_cost()


""" 
should this Digital Item be striped all these fields or should we lift it all and transfere it to models? 
should these field be transfered to product model or order model or both? i feel as if we are repeating ourselves here
"""
class DigitalItem(BaseItem):
    is_booklet = models.BooleanField(
        default=False,
        help_text=_("Check this if the item is a saddle-stitched or perfect-bound booklet.")
    )
    size = models.ForeignKey(ClientFacingSize, on_delete=models.SET_NULL, null=True, blank=True)
    number_of_pages = models.PositiveIntegerField(
        default=1,
        help_text=_("For booklets, this is the TOTAL number of pages including the cover (e.g., a 32pg inner + 4pg cover is 36 pages).")
    )
    digital_material = models.ForeignKey(
        DigitalPressMaterial,
        on_delete=models.PROTECT,
        help_text=_("The material for the inner pages of a booklet, or the material for a simple print.")
    )
    is_double_sided = models.BooleanField(
        default=False,
        help_text=_("For simple prints, is it double-sided? For booklets, does the COVER print on both sides?")
    )
    cover_material = models.ForeignKey(
        DigitalPressMaterial,
        on_delete=models.PROTECT,
        related_name='cover_jobs',
        null=True, blank=True,
        help_text=_("Optional: Select a different material for the booklet cover. If blank, the main material is used.")
    )
    cover_finishing_options = models.ManyToManyField(
        'products.FinishingService',
        related_name='cover_finishing_jobs',
        blank=True,
        help_text=_("Finishing applied ONLY to the cover (e.g., Lamination).")
    )

    @property
    def production_summary(self):
        """Generates a human-readable summary of how the item will be produced, including finishing."""
        # --- SIMPLE PRINT (NON-BOOKLET) ---
        if not self.is_booklet:
            items_per_sheet = self._calculate_imposition(
                self.digital_material.sheet_width_mm, self.digital_material.sheet_height_mm,
                self.final_width_mm, self.final_height_mm
            )
            if items_per_sheet == 0:
                return "Cannot fit on selected sheet."
            sheets_needed = math.ceil(self.quantity / items_per_sheet)
            summary = (f"{self.quantity} x items on {self.digital_material.name}. "
                       f"Prints {items_per_sheet}-up, requiring {sheets_needed} sheets. "
                       f"Printed {'double-sided' if self.is_double_sided else 'single-sided'}.")

            # Add finishing options
            finishes = self.finishing_options.all()
            if finishes:
                finish_names = ", ".join([f.name for f in finishes])
                summary += f"\n- Finishing: {finish_names}."
            return summary

        # --- BOOKLET LOGIC ---
        total_pages = self.number_of_pages
        if total_pages % 4 != 0:
            total_pages += (4 - total_pages % 4)
            page_note = f" (rounded up to {total_pages}pg for binding)"
        else:
            page_note = ""

        if total_pages <= 4:
            inner_pages = 0
            cover_sheets = math.ceil(total_pages / 4.0) * self.quantity
        else:
            inner_pages = total_pages - 4
            cover_sheets = 1 * self.quantity
        
        inner_sheets = math.ceil(inner_pages / 4.0) * self.quantity
        cover_mat = self.cover_material or self.digital_material

        # Build summary parts
        summary = f"{self.quantity} x {total_pages}-page Booklet{page_note}:\n"
        
        # Cover summary
        cover_summary = (f"- Cover: {cover_sheets} sheets of {cover_mat.name}, "
                         f"printed {'double-sided' if self.is_double_sided else 'single-sided'}.")
        cover_finishes = self.cover_finishing_options.all()
        if cover_finishes:
            finish_names = ", ".join([f.name for f in cover_finishes])
            cover_summary += f" Finishing: {finish_names}."
        summary += cover_summary

        # Inner pages summary
        if inner_sheets > 0:
            summary += f"\n- Inners: {inner_sheets} sheets of {self.digital_material.name}, printed double-sided."

        # Assembly/Booklet-wide finishing
        main_finishes = self.finishing_options.all()
        if main_finishes:
            finish_names = ", ".join([f.name for f in main_finishes])
            summary += f"\n- Assembly: {finish_names}."

        return summary

    def calculate_cost(self):
        """
        Calculates total cost. Handles simple prints and complex booklets separately.
        This version is hardened against None values in price fields.
        """
        if not self.machine or not self.digital_material:
            return Decimal('0.00')

        # --- BOOKLET COSTING LOGIC ---
        if self.is_booklet:
            total_pages = self.number_of_pages
            if total_pages % 4 != 0:
                total_pages = total_pages + (4 - total_pages % 4)

            inner_pages_cost = Decimal('0.00')
            cover_cost = Decimal('0.00')
            
            if total_pages > 4:
                inner_pages_count = total_pages - 4
                inner_sheets_needed = math.ceil(inner_pages_count / 4.0) * self.quantity
                try:
                    price_rule = DigitalPressPrice.objects.get(machine=self.machine, material=self.digital_material)
                    # FIX: Default to 0 if the price field is None
                    inner_price_per_sheet = price_rule.price_double_sided or Decimal('0.00')
                    inner_pages_cost = inner_sheets_needed * inner_price_per_sheet
                except DigitalPressPrice.DoesNotExist:
                    return Decimal('0.00')
            
            cover_material = self.cover_material or self.digital_material
            cover_sheets_needed = 1 * self.quantity
            try:
                price_rule = DigitalPressPrice.objects.get(machine=self.machine, material=cover_material)
                # FIX: Default to 0 if the price field is None
                if self.is_double_sided:
                    cover_price_per_sheet = price_rule.price_double_sided or Decimal('0.00')
                else:
                    cover_price_per_sheet = price_rule.price_single_sided or Decimal('0.00')
                cover_cost = cover_sheets_needed * cover_price_per_sheet
            except DigitalPressPrice.DoesNotExist:
                return Decimal('0.00')

            print_cost = inner_pages_cost + cover_cost
            
            finishing_cost = Decimal('0.00')
            for service in self.finishing_options.all():
                if service.calculation_method == FinishingService.CalculationMethod.PER_ITEM:
                    service_sub_cost = self.quantity * (service.simple_price or Decimal('0.00'))
                    finishing_cost += max(service_sub_cost, service.minimum_charge or Decimal('0.00'))
            for service in self.cover_finishing_options.all():
                if service.calculation_method == FinishingService.CalculationMethod.PER_SHEET_SINGLE_SIDED:
                     service_sub_cost = cover_sheets_needed * (service.simple_price or Decimal('0.00'))
                     finishing_cost += max(service_sub_cost, service.minimum_charge or Decimal('0.00'))
            
            total_cost = print_cost + finishing_cost
            min_charge_rule = DigitalPressPrice.objects.get(machine=self.machine, material=self.digital_material)
            # FIX: Default to 0 if minimum_charge is None
            minimum_charge = min_charge_rule.minimum_charge or Decimal('0.00')
            return max(total_cost, minimum_charge).quantize(Decimal('0.01'))

        # --- SIMPLE PRINT COSTING LOGIC (Non-Booklet) ---
        else:
            items_per_sheet = self._calculate_imposition(
                self.digital_material.sheet_width_mm, self.digital_material.sheet_height_mm,
                self.final_width_mm, self.final_height_mm
            )
            if items_per_sheet == 0: return Decimal('0.00')
            
            sheets_needed = math.ceil(self.quantity / items_per_sheet)
            try:
                price_rule = DigitalPressPrice.objects.get(machine=self.machine, material=self.digital_material)
                # FIX: Default to 0 if the price field is None
                if self.is_double_sided:
                    price_per_sheet = price_rule.price_double_sided or Decimal('0.00')
                else:
                    price_per_sheet = price_rule.price_single_sided or Decimal('0.00')
            except DigitalPressPrice.DoesNotExist:
                return Decimal('0.00')

            print_cost = sheets_needed * price_per_sheet
            
            finishing_cost = Decimal('0.00')
            for service in self.finishing_options.all():
                service_sub_cost = Decimal('0.00')
                service_price = service.simple_price or Decimal('0.00')
                if service.calculation_method == FinishingService.CalculationMethod.PER_SHEET_SINGLE_SIDED:
                    service_sub_cost = sheets_needed * service_price
                elif service.calculation_method == FinishingService.CalculationMethod.PER_ITEM:
                    service_sub_cost = self.quantity * service_price
                
                finishing_cost += max(service_sub_cost, service.minimum_charge or Decimal('0.00'))
                
            total_cost = print_cost + finishing_cost
            # FIX: Default to 0 if minimum_charge is None
            minimum_charge = price_rule.minimum_charge or Decimal('0.00')
            final_total = max(total_cost, minimum_charge)
            return final_total.quantize(Decimal('0.01')) 





def calculate_finish_cost(finish, qty, sheets_needed):
    if finish.calculation_method == finish.CalculationMethod.PER_ITEM:
        return max(
            qty * (finish.simple_price or Decimal("0.00")),
            finish.minimum_charge or Decimal("0.00"),
        )
    elif finish.calculation_method == finish.CalculationMethod.PER_SHEET_SINGLE_SIDED:
        return max(
            sheets_needed * (finish.simple_price or Decimal("0.00")),
            finish.minimum_charge or Decimal("0.00"),
        )
    return Decimal("0.00")


def calculate_starting_price(product_template):
    if not product_template.available_materials.exists() or not product_template.final_size:
        return None

    qty = product_template.minimum_order_quantity
    lowest_total = None

    for material in product_template.available_materials.all():
        try:
            price_rule = DigitalPressPrice.objects.get(
                material=material, machine__company=product_template.company
            )
        except DigitalPressPrice.DoesNotExist:
            continue

        items_per_sheet = product_template.company.calculate_imposition(
            sheet_width=material.sheet_width_mm,
            sheet_height=material.sheet_height_mm,
            final_width=product_template.final_size.width_mm,
            final_height=product_template.final_size.height_mm,
        )
        if not items_per_sheet:
            continue

        sheets_needed = math.ceil(qty / items_per_sheet)

        for side_price in [price_rule.price_single_sided, price_rule.price_double_sided]:
            if side_price is None:
                continue

            base_price = sheets_needed * side_price
            finish_total = sum(
                calculate_finish_cost(f, qty, sheets_needed)
                for f in product_template.mandatory_finishes.all()
            )

            total_cost = base_price + finish_total
            total_cost = max(total_cost, price_rule.minimum_charge or Decimal("0.00"))

            if lowest_total is None or total_cost < lowest_total:
                lowest_total = total_cost

    return lowest_total
