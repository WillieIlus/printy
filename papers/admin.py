from django.contrib import admin
from .models import (
    ProductionPaperSize,
    FinalPaperSize,
    PaperType,
    LargeFormatMaterial,
    UVDTFMaterial,
)

# A base admin class for shared paper size configurations
class BaseSizeAdmin(admin.ModelAdmin):
    """Base admin configuration for paper size models."""
    list_display = ('name', 'width_mm', 'height_mm')
    search_fields = ('name',)
    ordering = ('name',)
    
    # Organize fields into sections for a cleaner form
    fieldsets = (
        (None, {
            'fields': ('name', ('width_mm', 'height_mm'))
        }),
    )

    def save_model(self, request, obj, form, change):
        """
        Automatically sets the size_type based on the model.
        This field is defined in the abstract BaseSize model but is not
        meant to be edited by the user in the admin panel.
        """
        if isinstance(obj, ProductionPaperSize):
            obj.size_type = self.model.PRODUCTION
        elif isinstance(obj, FinalPaperSize):
            obj.size_type = self.model.FINAL
        super().save_model(request, obj, form, change)

@admin.register(ProductionPaperSize)
class ProductionPaperSizeAdmin(BaseSizeAdmin):
    """Admin configuration for Production Paper Sizes."""
    pass

@admin.register(FinalPaperSize)
class FinalPaperSizeAdmin(BaseSizeAdmin):
    """Admin configuration for Final Paper Sizes."""
    pass

@admin.register(PaperType)
class PaperTypeAdmin(admin.ModelAdmin):
    """Admin configuration for Digital Paper Types."""
    list_display = ('name', 'gsm', 'is_coated', 'is_banner', 'is_special', 'default_size')
    list_filter = ('is_coated', 'is_banner', 'is_special', 'default_size')
    search_fields = ('name', 'gsm')
    ordering = ('name', 'gsm')

    fieldsets = (
        (None, {
            'fields': ('name', 'gsm', 'default_size')
        }),
        ('Properties', {
            'fields': ('is_coated', 'color')
        }),
        ('Special Types', {
            'description': "Flags for special material types.",
            'fields': ('is_banner', 'is_special')
        }),
    )

@admin.register(LargeFormatMaterial)
class LargeFormatMaterialAdmin(admin.ModelAdmin):
    """Admin configuration for Large Format Materials."""
    list_display = ('name', 'material_type', 'thickness_mm', 'width_mm')
    list_filter = ('material_type',)
    search_fields = ('name', 'material_type')
    ordering = ('name',)
    
    fieldsets = (
        (None, {
            'fields': ('name', 'material_type')
        }),
        ('Specifications (mm)', {
            'fields': (('thickness_mm', 'width_mm'),)
        }),
    )

@admin.register(UVDTFMaterial)
class UVDTFMaterialAdmin(admin.ModelAdmin):
    """Admin configuration for UV DTF Materials."""
    list_display = ('name', 'finish')
    search_fields = ('name', 'finish')
    ordering = ('name',)
