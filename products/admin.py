from django.contrib import admin
from .models import ProductImage, ProductTemplate #, Review


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ("product", "alt_text", "order")
    list_filter = ("product",)
    search_fields = ("product__name", "alt_text")


# @admin.register(ProductCategory)
# class ProductCategoryAdmin(admin.ModelAdmin):
#     list_display = ("name", "slug")
#     search_fields = ("name",)
#     prepopulated_fields = {"slug": ("name",)}


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1  # Number of empty forms to display


@admin.register(ProductTemplate)
class ProductTemplateAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "company",
        "category",
        "is_active",
        "is_popular",
        "starting_price",
    )
    list_filter = ("company", "category", "is_active", "is_popular", "is_featured")
    search_fields = ("name", "description", "slug")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at", "updated_at", "starting_price")
    filter_horizontal = (
        "cover_range_gsm",
        "insert_range_gsm",
        "mandatory_finishings",
        "optional_finishings",
    )
    inlines = [ProductImageInline]


# @admin.register(Review)
# class ReviewAdmin(admin.ModelAdmin):
#     list_display = ("product", "user", "rating", "created_at")
#     list_filter = ("rating", "product", "user")
#     search_fields = ("product__name", "user__username", "comment")
#     readonly_fields = ("created_at",)