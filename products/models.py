# products/models.py
import uuid
from decimal import Decimal

from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from core.models import PrintCompany
from papers.models import PaperType, FinalPaperSize
from machines.models import Machine


class ProductImage(models.Model):
    """
    Represents an image for a product.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(  # <-- You referenced `self.product` in __str__, so this FK is needed
        "ProductTemplate",
        on_delete=models.CASCADE,
        related_name="additional_images",
        verbose_name=_("product"),
    )
    image = models.ImageField(_("image"), upload_to="product_images/")
    alt_text = models.CharField(_("alt text"), max_length=255, blank=True)
    order = models.PositiveIntegerField(
        _("order"),
        default=0,
        help_text=_("Display order of the image."),
    )

    class Meta:
        ordering = ["order"]
        verbose_name = _("product image")
        verbose_name_plural = _("product images")

    def __str__(self):
        return self.alt_text or f"Image for {self.product.name}"


class ProductCategory(models.Model):
    """
    Represents a category for products (e.g., Business Cards, Flyers).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_("name"), max_length=100, unique=True)
    slug = models.SlugField(
        _("slug"),
        max_length=100,
        unique=True,
        blank=True,
        db_index=True,
    )

    class Meta:
        verbose_name = _("product category")
        verbose_name_plural = _("product categories")

    def save(self, *args, **kwargs):
        """Automatically generates a slug from the category name."""
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class ProductTemplate(models.Model):
    """
    Product template for guided ordering.
    Contains constraints, available options, and visual presentation.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        PrintCompany,
        on_delete=models.CASCADE,
        related_name="products",
        verbose_name=_("company"),
    )
    category = models.ForeignKey(
        ProductCategory,
        on_delete=models.PROTECT,
        related_name="products",
        verbose_name=_("category"),
    )
    name = models.CharField(_("name"), max_length=255)  # e.g. "A4 Booklet"
    slug = models.SlugField(_("slug"), max_length=255, blank=True, unique=True, db_index=True)
    description = models.TextField(_("description"), blank=True)

    size = models.ForeignKey(FinalPaperSize, on_delete=models.CASCADE, verbose_name=_("size"))  # Fixed typo
    deliverable = models.CharField(_("deliverable"), max_length=50)  # e.g. "Booklet", "Flyer"

    # Paper ranges
    cover_range_gsm = models.ManyToManyField(PaperType, related_name="cover_templates")
    insert_range_gsm = models.ManyToManyField(PaperType, related_name="insert_templates")

    # Rules
    page_step = models.PositiveIntegerField(default=2, help_text=_("Enforce even pages (e.g., 4 pages for booklets)."))

    # Mandatory & optional finishes
    mandatory_finishings = models.ManyToManyField(Machine, related_name="mandatory_templates", blank=True)
    optional_finishings = models.ManyToManyField(Machine, related_name="optional_templates", blank=True)

    minimum_order_quantity = models.PositiveIntegerField(default=100, verbose_name=_("minimum order quantity"))
    is_active = models.BooleanField(default=True, verbose_name=_("is active"))
    is_popular = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False, verbose_name=_("is featured"))

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("digital template")
        verbose_name_plural = _("digital templates")
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def main_image(self):
        """Returns the main product image (order 0) or None."""
        first_image = self.additional_images.order_by("order").first()
        return first_image.image if first_image else None

    def get_mandatory_finishings(self):
        return self.mandatory_finishings.all()

    def get_optional_finishings(self):
        return self.optional_finishings.all()

    @property
    def starting_price(self):
        from engine.services.products import product_starting_price
        price = product_starting_price(self)
        if price is None:
            return _("Request Quote")
        return f"From KES {price.quantize(Decimal('0.01'))}"


# class Review(models.Model):
#     product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="reviews")
#     user = models.ForeignKey(User, on_delete=models.CASCADE)
#     rating = models.PositiveIntegerField(default=5)
#     comment = models.TextField()
#     created_at = models.DateTimeField(auto_now_add=True)