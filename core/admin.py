from django.contrib import admin
from .models import PrintCompany, ClientProfile, CompanyStaffProfile

@admin.register(PrintCompany)
class PrintCompanyAdmin(admin.ModelAdmin):
    """Admin configuration for the PrintCompany model."""
    # Fields to display in the list view
    list_display = ('name', 'website', 'phone', 'email', 'is_active')
    
    # Filters on the right sidebar
    list_filter = ('is_active',)
    
    # Fields to search by
    search_fields = ('name', 'email', 'phone')
    
    # Automatically generate the slug from the name field
    prepopulated_fields = {'slug': ('name',)}
    
    # Read-only fields
    readonly_fields = ('created_at', 'updated_at')
    
    # Organize fields into sections for the edit form
    fieldsets = (
        (None, {
            'fields': ('name', 'slug', 'logo', 'description')
        }),
        ('Contact Information', {
            'fields': ('website', 'phone', 'email', 'address')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )

@admin.register(ClientProfile)
class ClientProfileAdmin(admin.ModelAdmin):
    """Admin configuration for the ClientProfile model."""
    # Use autocomplete for the user field for better performance
    autocomplete_fields = ('user',)
    
    # Display related user info and optimize database queries
    list_display = ('user', 'get_user_email', 'company_name')
    list_select_related = ('user',)
    
    # Fields to search by (including related user fields)
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'company_name')

    @admin.display(description='User Email', ordering='user__email')
    def get_user_email(self, obj):
        return obj.user.email

@admin.register(CompanyStaffProfile)
class CompanyStaffProfileAdmin(admin.ModelAdmin):
    """Admin configuration for the CompanyStaffProfile model."""
    # Use autocomplete for foreign keys for better performance
    autocomplete_fields = ('user', 'company')
    
    # Display related info and optimize database queries
    list_display = ('user', 'company', 'job_title')
    list_select_related = ('user', 'company')
    
    # Filters on the right sidebar
    list_filter = ('company',)
    
    # Fields to search by
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'company__name', 'job_title')