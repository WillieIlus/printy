       
class ScreenPrintItem(BaseItem):
    """A Screen Printing job."""
    screen_setup = models.ForeignKey(ScreenSetup, on_delete=models.PROTECT)
    number_of_colors = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    # You might add fields like item_description (e.g., "White Cotton T-Shirt")

    def calculate_cost(self):
        """Screen print calculation: setup cost + run cost + finishing."""
        if not self.screen_setup:
            return Decimal('0.00')

        setup_cost = self.screen_setup.setup_cost_per_screen * self.number_of_colors

        try:
            # Assumes a single, company-wide run price for screen printing.
            # This could be refined to be material-specific if needed.
            run_price_rule = ScreenRunPrice.objects.filter(printer=self.job.printer).latest('id')
            run_cost = self.quantity * run_price_rule.run_cost_per_item_per_color * self.number_of_colors
            effective_run_cost = max(run_cost, run_price_rule.minimum_charge)
        except ScreenRunPrice.DoesNotExist:
            effective_run_cost = Decimal('0.00')

        print_cost = setup_cost + effective_run_cost
        
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
            
            finishing_cost += max(service_sub_cost, service.minimum_charge)

        total_cost = print_cost + finishing_cost
        
        return total_cost.quantize(Decimal('0.01'))
    
    @property
    def production_summary(self):
        """Generates a production summary including screens, colors, and finishing."""
        if not self.screen_setup:
            return "Screen setup type not specified."

        summary = (
            f"Screen print run of {self.quantity} items.\n"
            f"- Setup: {self.number_of_colors} x {self.screen_setup.name} screens required for a {self.number_of_colors}-color job."
        )
        
        # Add finishing options
        finishes = self.finishing_options.all()
        if finishes:
            finish_names = ", ".join([f.name for f in finishes])
            summary += f"\n- Finishing: {finish_names}."

        return summary
    
