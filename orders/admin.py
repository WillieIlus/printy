#orders/admin.py
from django.contrib import admin
from .models import Order, JobDeliverable, DeliverableFinishing

class DeliverableFinishingInline(admin.StackedInline):
    model = DeliverableFinishing
    autocomplete_fields = ("service",)
    extra = 1

class JobDeliverableInline(admin.TabularInline):
    """
    Compact inline for viewing/adding JobDeliverables directly on the Order page.
    Provides a link to the full edit page for each deliverable.
    """
    model = JobDeliverable
    fields = ('name', 'quantity', 'size', 'is_booklet', 'page_count', 'total_price')
    readonly_fields = ('name', 'size', 'is_booklet', 'page_count', 'total_price')
    show_change_link = True
    extra = 0  # Don't show extra forms by default, as they are complex

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return True

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """Admin configuration for the Order model."""
    list_display = ('job_ref', 'name', 'client', 'printer', 'status', 'created_at', 'display_total_price')
    list_filter = ('status', 'printer', 'client')
    search_fields = ('job_ref', 'name', 'client__email', 'printer__name')
    ordering = ('-created_at',)
    
    # Use autocomplete fields for foreign keys for better performance
    autocomplete_fields = ('client', 'printer')
    
    # Make auto-generated fields read-only
    readonly_fields = ('job_ref', 'created_at', 'display_total_price')
    
    # Include the deliverables inline on the order page
    inlines = [JobDeliverableInline]

    # Organize the form into logical sections
    fieldsets = (
        (None, {
            'fields': ('job_ref', 'name', 'status')
        }),
        ('Parties Involved', {
            'fields': ('client', 'printer')
        }),
        ('Pricing & Notes', {
            'fields': ('display_total_price', 'notes')
        }),
        ('Timestamps', {
            'fields': ('created_at',)
        }),
    )

    @admin.display(description='Total Price')
    def display_total_price(self, obj):
        # Format the total price with currency for display
        currency = "KES"  # Assuming Kenyan Shillings as per location
        return f"{obj.total_price()} {currency}"

@admin.register(JobDeliverable)
class JobDeliverableAdmin(admin.ModelAdmin):
    list_display = ('name', 'order', 'quantity', 'is_booklet', 'display_total_price')
    list_filter = ('order__printer', 'is_booklet', 'size')
    search_fields = ('name', 'order__job_ref', 'order__name')

    # ✅ only include methods if they’re actually defined in this class
    readonly_fields = ('total_price', 'display_total_price', 'display_production_summary')

    autocomplete_fields = (
        'order', 'size', 'cover_machine', 'cover_material', 'inner_machine', 'inner_material'
    )
    inlines = [DeliverableFinishingInline]

    fieldsets = (
        ('Core Details', {
            'fields': ('order', 'name', 'quantity', 'size')
        }),
        ('Calculations', {
            'fields': ('total_price', 'display_total_price', 'display_production_summary')
        }),
        ('Primary Specifications (for all jobs)', {
            'fields': ('inner_machine', 'inner_material', 'inner_sidedness')
        }),
        ('Booklet Specifications', {
            'classes': ('collapse',),
            'fields': ('is_booklet', 'page_count', 'binding')
        }),
        ('Cover Specifications (Booklets Only)', {
            'classes': ('collapse',),
            'fields': ('cover_machine', 'cover_material', 'cover_sidedness')
        }),
        ('Imposition Settings (Advanced)', {
            'classes': ('collapse',),
            'fields': ('bleed_mm', 'gutter_mm', 'gripper_mm')
        }),
    )

    # ✅ define the admin methods correctly
    @admin.display(description='Total Price')
    def display_total_price(self, obj):
        currency = "KES"
        return f"{obj.total_price} {currency}"

    @admin.display(description='Production Summary')
    def display_production_summary(self, obj):
        return obj.production_summary()


@admin.display(description='Total Price')
def display_total_price(self, obj):
    currency = "KES"  # fallback
    if obj.inner_material and hasattr(obj.inner_material, "digital_prices"):
        price_rule = obj.inner_material.digital_prices.first()
        if price_rule:
            currency = price_rule.currency
    return f"{obj.total_price} {currency}"


@admin.display(description='Production Summary')
def display_production_summary(self, obj):
    # Calls the production_summary() method from your JobDeliverable model 
    return obj.production_summary()

def save_model(self, request, obj, form, change):
    # Validate required fields for flat jobs
    if not obj.is_booklet and (not obj.inner_machine or not obj.inner_material):
        raise ValueError("Flat jobs must have an inner machine and material selected.")

    # Validate required fields for booklets
    if obj.is_booklet and (not obj.cover_machine or not obj.cover_material):
        raise ValueError("Booklets must have both cover and inner machine/material selected.")

    super().save_model(request, obj, form, change)
