# pricing/base_item.py
        
class LargeFormatItem(BaseItem):
    """A Large Format job."""
    large_format_material = models.ForeignKey(LargeFormatMaterial, on_delete=models.PROTECT)
    final_width_m = models.DecimalField(max_digits=5, decimal_places=2)
    final_height_m = models.DecimalField(max_digits=5, decimal_places=2)
    
    @property
    def material_usage_details(self):
        """
        Calculates and returns a readable string describing the total material area used.
        """
        # This logic is extracted directly from your calculate_cost method
        final_width_m = self.final_width_m
        final_height_m = self.final_height_m
        roll_width_m = self.large_format_material.roll_width_m
        
        total_printed_area_sq_m = Decimal('0.00')

        if self.is_tiled and final_height_m > roll_width_m:
            number_of_tiles = math.ceil(final_height_m / roll_width_m)
            if number_of_tiles > 1:
                number_of_seams = number_of_tiles - 1
                overlap_m = Decimal(self.tile_overlap_mm) / Decimal(1000)
                total_overlap_height = number_of_seams * overlap_m
                total_printed_height_m = final_height_m + total_overlap_height
                total_printed_area_sq_m = final_width_m * total_printed_height_m
            else:
                total_printed_area_sq_m = final_width_m * final_height_m
        else:
            total_printed_area_sq_m = final_width_m * final_height_m
            
        return f"Total material to be printed: {total_printed_area_sq_m.quantize(Decimal('0.01'))} m²"


    @property
    def material_usage_details(self):
        """
        Calculates total printed area and estimates waste by trying to nest items.
        """
        if not self.dimensions_list:
            return "No dimensions provided."

        roll_width_m = self.large_format_material.roll_width_m
        total_printed_area = Decimal('0.0')
        total_length_used = Decimal('0.0')

        # Simple nesting logic: Sort by height and place items one by one.
        sorted_items = sorted(self.dimensions_list, key=lambda x: x['height_m'], reverse=True)
        
        for item in sorted_items:
            width = Decimal(str(item['width_m']))
            height = Decimal(str(item['height_m']))
            quantity = item.get('quantity', 1)

            if height > roll_width_m:
                # This logic could be expanded to handle rotation if needed
                return f"Error: Item height ({height}m) exceeds roll width ({roll_width_m}m)."
            
            total_printed_area += width * height * quantity
            total_length_used += width * quantity # Adds the length of each item to the total roll length used

        total_material_area = total_length_used * roll_width_m
        waste = total_material_area - total_printed_area

        return (
            f"Total Printed Area: {total_printed_area.quantize(Decimal('0.01'))} m². "
            f"Total Material Used: {total_material_area.quantize(Decimal('0.01'))} m². "
            f"Estimated Waste: {waste.quantize(Decimal('0.01'))} m²."
        )


    def calculate_cost(self):
        """Calculates total cost, including finishing options and minimum charges."""
        if not self.large_format_material:
            return Decimal('0.00')
        
        # Ensure item can physically be printed on the roll
        roll_width_m = self.large_format_material.roll_width_m
        if self.final_width_m > roll_width_m and self.final_height_m > roll_width_m:
            return Decimal('0.00') # Cannot be rotated to fit

        item_area_sq_m = self.final_width_m * self.final_height_m
        total_printed_area = item_area_sq_m * self.quantity
        print_cost = total_printed_area * self.large_format_material.price_per_sq_meter

        # --- Finishing Cost Logic ---
        finishing_cost = Decimal('0.00')
        for service in self.finishing_options.all():
            service_sub_cost = Decimal('0.00')
            
            if service.pricing_method == FinishingService.PricingMethod.TIERED:
                try:
                    # Tiered pricing for large format is based on total quantity of items
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
        
        # Ensure the final total respects the minimum charge for the material
        final_total = max(total_cost, self.large_format_material.minimum_charge)

        return final_total.quantize(Decimal('0.01'))
    
    @property
    def production_summary(self):
        """Calculates material usage and lists finishing services for a large format job."""
        if not self.large_format_material:
            return "Material not selected."

        # (Calculation logic remains the same)
        roll_width_m = self.large_format_material.roll_width_m
        item_w, item_h = self.final_width_m, self.final_height_m
        oriented_w, oriented_l = (item_w, item_h) if item_w <= item_h else (item_h, item_w)
        orientation_note = "(rotated)" if item_w > item_h else ""

        if oriented_w > roll_width_m:
            return f"Error: Item dimension ({oriented_w}m) exceeds roll width ({roll_width_m}m)."

        items_across = math.floor(roll_width_m / oriented_w)
        rows_needed = math.ceil(self.quantity / items_across)
        total_length_used = rows_needed * oriented_l
        
        summary = (
            f"{self.quantity}x items ({item_w}m x {item_h}m) on {self.large_format_material.name} {orientation_note}.\n"
            f"Nesting {items_across}-up on a {roll_width_m}m wide roll.\n"
            f"Total roll length needed: {total_length_used:.2f}m."
        )

        # Add finishing options
        finishes = self.finishing_options.all()
        if finishes:
            finish_names = ", ".join([f.name for f in finishes])
            summary += f"\n- Finishing: {finish_names}."
            
        return summary
