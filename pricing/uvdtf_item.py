    
class UVDTFItem(BaseItem):
    """A UV DTF Print job."""
    uv_dtf_material = models.ForeignKey(UVDTFMaterial, on_delete=models.PROTECT)
    final_width_mm = models.PositiveIntegerField()
    final_height_mm = models.PositiveIntegerField()

    def calculate_cost(self):
        """UV DTF calculation: area-based cost + finishing + minimum charge."""
        if not self.uv_dtf_material:
            return Decimal('0.00')

        item_area_sq_m = (Decimal(self.final_width_mm) * Decimal(self.final_height_mm)) / Decimal('1000000')
        total_printed_area = item_area_sq_m * self.quantity
        print_cost = total_printed_area * self.uv_dtf_material.price_per_sq_meter

        # --- Finishing Cost Logic ---
        finishing_cost = Decimal('0.00')
        for service in self.finishing_options.all():
            service_sub_cost = Decimal('0.00')
            if service.pricing_method == FinishingService.PricingMethod.TIERED:
                try:
                    # Tiered pricing based on quantity of items
                    tier = service.price_tiers.get(min_quantity__lte=self.quantity, max_quantity__gte=self.quantity)
                    service_sub_cost = tier.price
                except TieredPrice.DoesNotExist:
                    service_sub_cost = Decimal('0.00')
            else: # Simple Pricing
                if service.calculation_method == FinishingService.CalculationMethod.PER_ITEM:
                    service_sub_cost = self.quantity * service.simple_price
                elif service.calculation_method == FinishingService.CalculationMethod.PER_SQ_METER:
                    service_sub_cost = total_printed_area * service.simple_price

            finishing_cost += max(service_sub_cost, service.minimum_charge)
        
        total_cost = print_cost + finishing_cost
        
        # Apply the overall material minimum charge to the total cost
        final_total = max(total_cost, self.uv_dtf_material.minimum_charge)

        return final_total.quantize(Decimal('0.01'))
    
    @property
    def production_summary(self):
        """Generates a summary of material usage and any finishing services."""
        if not self.uv_dtf_material:
            return "UV DTF Material not specified."

        item_area_sq_m = (Decimal(self.final_width_mm) * Decimal(self.final_height_mm)) / Decimal('1000000')
        total_printed_area_sq_m = item_area_sq_m * self.quantity

        summary = (
            f"{self.quantity} x UV DTF transfers ({self.final_width_mm}mm x {self.final_height_mm}mm).\n"
            f"- Material: {self.uv_dtf_material.name}.\n"
            f"- Total Printed Area: {total_printed_area_sq_m.quantize(Decimal('0.0001'))} m²."
        )
        
        # Add finishing options
        finishes = self.finishing_options.all()
        if finishes:
            finish_names = ", ".join([f.name for f in finishes])
            summary += f"\n- Finishing: {finish_names}."

        return summary
  
