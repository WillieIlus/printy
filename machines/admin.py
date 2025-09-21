from django.contrib import admin
from .models import Machine, ServiceCategory, MachineType

@admin.register(ServiceCategory)
class ServiceCategoryAdmin(admin.ModelAdmin):
    """Admin configuration for Service Categories."""
    list_display = ('name', 'description')
    search_fields = ('name',)
    # Automatically generate the slug from the name field for convenience
    prepopulated_fields = {'slug': ('name',)}

@admin.register(Machine)
class MachineAdmin(admin.ModelAdmin):
    """Admin configuration for Machines."""
    list_display = ('name', 'company', 'machine_type')
    list_filter = ('company', 'machine_type')
    search_fields = ('name', 'company__name')
    ordering = ('company', 'name')
    
    # Use autocomplete for the company foreign key for better performance
    autocomplete_fields = ('company',)
    
    # Use a more user-friendly interface for the many-to-many relationship
    filter_horizontal = ('supported_sizes',)
    
    # Organize the form fields into logical sections
    fieldsets = (
        (None, {
            'fields': ('company', 'name', 'machine_type')
        }),
        ('Size Capabilities', {
            'description': "Select the standard sizes this machine supports, or allow custom sizes.",
            'fields': ('supported_sizes', 'supports_client_custom_size')
        }),
    )
