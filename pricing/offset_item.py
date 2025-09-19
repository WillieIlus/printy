#pricing/offset_item.py
    """
    I think we need to remove the model fields and transfere them to either order models or product template or both and let the logic do for both models,
    """
class OffsetPrintItem(BaseItem):
    """An Offset Print job."""
    offset_material = models.ForeignKey(DigitalPressMaterial, on_delete=models.PROTECT)
    size = models.ForeignKey(ClientFacingSize, on_delete=models.SET_NULL, null=True, blank=True)
    plate_type = models.ForeignKey(OffsetPlatePrice, on_delete=models.PROTECT)
    number_of_colors = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])

    def calculate_cost(self):
        """Offset calculation: high setup cost (plates) + low running cost + finishing."""
        if not self.plate_type or not self.offset_material:
            return Decimal('0.00')

        setup_cost = self.plate_type.plate_setup_cost * self.number_of_colors

        items_per_sheet = self._calculate_imposition(
            self.offset_material.sheet_width_mm,
            self.offset_material.sheet_height_mm,
            self.final_width_mm,
            self.final_height_mm
        )
        if items_per_sheet == 0:
            return Decimal('0.00')

        sheets_needed = math.ceil(self.quantity / items_per_sheet)

        try:
            run_price_rule = OffsetRunPrice.objects.get(material=self.offset_material)
            run_cost_per_sheet_base = run_price_rule.price_per_sheet_per_color
            minimum_run_charge = run_price_rule.minimum_run_charge
        except OffsetRunPrice.DoesNotExist:
            run_cost_per_sheet_base = Decimal('0.00')
            minimum_run_charge = Decimal('0.00')

        total_run_cost = sheets_needed * run_cost_per_sheet_base * self.number_of_colors
        effective_run_cost = max(total_run_cost, minimum_run_charge)

        print_cost = setup_cost + effective_run_cost

        # --- Finishing Cost Logic ---
        finishing_cost = Decimal('0.00')
        for service in self.finishing_options.all():
            service_sub_cost = Decimal('0.00')
            if service.pricing_method == FinishingService.PricingMethod.TIERED:
                try:
                    # Tiered pricing based on number of sheets
                    tier = service.price_tiers.get(min_quantity__lte=sheets_needed, max_quantity__gte=sheets_needed)
                    service_sub_cost = tier.price
                except TieredPrice.DoesNotExist:
                    service_sub_cost = Decimal('0.00')
            else: # Simple Pricing
                if service.calculation_method == FinishingService.CalculationMethod.PER_SHEET_SINGLE_SIDED:
                    service_sub_cost = sheets_needed * service.simple_price
                elif service.calculation_method == FinishingService.CalculationMethod.PER_ITEM:
                    service_sub_cost = self.quantity * service.simple_price
            
            finishing_cost += max(service_sub_cost, service.minimum_charge)
            
        total_cost = print_cost + finishing_cost

        return total_cost.quantize(Decimal('0.01'))
    
    @property
    def production_summary(self):
        """Generates a production summary including plates, sheets, and finishing."""
        if not self.offset_material or not self.plate_type:
            return "Material or plate type not specified."

        items_per_sheet = self._calculate_imposition(
            self.offset_material.sheet_width_mm, self.offset_material.sheet_height_mm,
            self.final_width_mm, self.final_height_mm
        )
        if items_per_sheet == 0:
            return "Cannot fit on selected sheet."
        sheets_needed = math.ceil(self.quantity / items_per_sheet)
        
        summary = (
            f"{self.quantity} x items ({self.final_width_mm}mm x {self.final_height_mm}mm) on {self.offset_material.name}.\n"
            f"- Production: Prints {items_per_sheet}-up, requiring {sheets_needed} sheets.\n"
            f"- Plates: {self.number_of_colors} x {self.plate_type.name} plates required for a {self.number_of_colors}-color job."
        )

        # Add finishing options
        finishes = self.finishing_options.all()
        if finishes:
            finish_names = ", ".join([f.name for f in finishes])
            summary += f"\n- Finishing: {finish_names}."

        return summary
