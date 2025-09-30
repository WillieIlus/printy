from django.contrib import admin
# Cleaned up imports
from .models import PrintCompany, ServiceCategory, PortfolioItem 
from core.models import ServiceCategory
 
@admin.register(ServiceCategory)
class ServiceCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'description')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}
    fieldsets = (
        (None, {
            'fields': ('name', 'slug', 'description'),
            'description': """
                <p class="help">
                    <b>What are Service Categories?</b><br>
                    These are tags used to classify your company. 
                    Examples: <em>'Digital Printing', 'Book Binding', 'Promotional Items'</em>.
                </p>
            """
        }),
    )

class PortfolioItemInline(admin.TabularInline):
    model = PortfolioItem
    extra = 1
    fields = ('image', 'title', 'description', 'date_completed', 'is_featured')
    verbose_name = "Portfolio Project"
    verbose_name_plural = "Portfolio Projects"
    
@admin.register(PrintCompany)
class PrintCompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'website', 'phone', 'is_active')
    list_filter = ('is_active', 'services')
    search_fields = ('name', 'owner__email', 'phone')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('created_at', 'updated_at')
    inlines = [PortfolioItemInline]
    
    # CORRECTED and MERGED fieldsets
    fieldsets = (
        (None, {
            'fields': ('owner', 'name', 'slug'),
            'description': """
                <p class="help">
                    <b>Welcome to your Company Profile!</b><br>
                    This is where you control all the public information about your business.
                </p>
            """
        }),
        ('Company Description', {
            'fields': ('description',),
        }),
        ('Branding & Page Theme 🎨', {
            'classes': ('collapse',),
            'fields': ('logo', 'primary_color', 'secondary_color'),
        }),
        ('Services Offered', {
            'fields': ('services',),
            'description': "<p class='help'>Select all service categories that your company provides.</p>"
        }),
        ('Contact & Location 📍', {
            'fields': ('website', 'phone', 'email', 'address', 'latitude', 'longitude'),
            'description': "<p class='help'>Latitude and Longitude are crucial for the map feature.</p>"
        }),
        ('Operational Status', {
            'fields': ('current_busy_level', 'is_active'),
             'description': "<p class='help'>Set your current production capacity and public visibility.</p>"
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    
    