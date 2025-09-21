from django.contrib import admin
from .models import Order, JobDeliverable, DeliverableFinishing

class DeliverableFinishingInline(admin.TabularInline):
    """
    Inline admin for managing finishing services on a JobDeliverable.
    Allows adding/editing finishings directly on the deliverable's page.
    """
    model = DeliverableFinishing
    # Use autocomplete for the service for better performance and usability
    autocomplete_fields = ('service',)
    extra = 1  # Show one empty slot for adding a new finishing service

class JobDeliverableInline(admin.TabularInline):
    """
    Compact inline for viewing/adding JobDeliverables directly on the Order page.
    Provides a link to the full edit page for each deliverable.
    """
    model = JobDeliverable
    # Display a concise set of fields in the order view
    fields = ('name', 'quantity', 'size', 'is_booklet', 'page_count')
    readonly_fields = ('name', 'quantity', 'size', 'is_booklet', 'page_count')
    # Link to the full change form for detailed editing
    show_change_link = True
    extra = 0 # Don't show extra forms by default, as they are complex

    def has_add_permission(self, request, obj=None):
        # Disable adding deliverables directly from the order inline
        # to encourage using the full form for this complex model.
        return False

    def has_delete_permission(self, request, obj=None):
        # Allow deletion from the order page
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
        # This assumes a single currency for the order for simplicity.
        currency = "KES"
        return f"{obj.total_price()} {currency}"

@admin.register(JobDeliverable)
class JobDeliverableAdmin(admin.ModelAdmin):
    """
    Detailed admin configuration for the JobDeliverable model.
    This page is used for in-depth editing of a single deliverable.
    """
    list_display = ('name', 'order', 'quantity', 'size', 'is_booklet')
    list_filter = ('order__printer', 'is_booklet', 'size')
    search_fields = ('name', 'order__job_ref', 'order__name')
    
    # Use autocomplete fields for all foreign keys
    autocomplete_fields = (
        'order', 'size', 'cover_machine', 'cover_material', 'inner_machine', 'inner_material'
    )
    
    # Use the inline for managing finishing services
    inlines = [DeliverableFinishingInline]
    
    # Organize the very complex form into logical, collapsible sections
    fieldsets = (
        ('Core Details', {
            'fields': ('order', 'name', 'quantity', 'size')
        }),
        ('Booklet Specifications', {
            'classes': ('collapse',),
            'fields': ('is_booklet', 'page_count', 'binding')
        }),
        ('Cover Specifications', {
            'classes': ('collapse',),
            'description': "These fields are primarily for booklets.",
            'fields': ('cover_machine', 'cover_material', 'cover_sidedness')
        }),
        ('Inner Pages Specifications', {
            'classes': ('collapse',),
            'fields': ('inner_machine', 'inner_material', 'inner_sidedness')
        }),
        ('Imposition Settings (Advanced)', {
            'classes': ('collapse',),
            'description': "Adjust the bleed and spacing for print production.",
            'fields': ('bleed_mm', 'gutter_mm', 'gripper_mm')
        }),
    )
