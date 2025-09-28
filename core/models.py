import uuid
from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from accounts.models import User

from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal

class ServiceCategory(models.Model):
    """
    A high-level category of service that a print company can offer,
    used for filtering and finding similar companies.
    e.g., 'Digital Printing', 'Offset Printing', 'Book Binding'.
    """
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text=_("The name of the service category (e.g., 'Screen Printing').")
    )
    slug = models.SlugField(
        max_length=100,
        unique=True,
        blank=True,
        help_text=_("A URL-friendly version of the name (auto-generated).")
    )
    description = models.TextField(
        blank=True,
        null=True,
        help_text=_("A brief description of what this service category entails.")
    )

    class Meta:
        verbose_name = _("Service Category")
        verbose_name_plural = _("Service Categories")
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
    
    
class PrintCompany(models.Model):
    """
    Represents the entire print shop, combining profile, assets, 
    and operational settings like production timelines.
    """
    class BusyLevel(models.IntegerChoices):
        LEAST_BUSY = 1, _('Least Busy (Faster Turnaround)')
        LESS_BUSY = 2, _('Less Busy')
        AVERAGE = 3, _('Average')
        BUSY = 4, _('Busy')
        VERY_BUSY = 5, _('Very Busy (Longer Turnaround)')

    # --- Core Identity & Ownership ---
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='owned_print_company',
        help_text=_("The user account that owns and manages this company.")
    )
    name = models.CharField(_("Company Name"), max_length=255, unique=True)
    slug = models.SlugField(max_length=255, unique=True, blank=True, db_index=True)
    description = models.TextField(blank=True, null=True)
    logo = models.ImageField(upload_to="company_logos/", blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    address = models.CharField(max_length=255, blank=True, null=True)
    latitude = models.DecimalField(_("latitude (Y)"), max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(_("longitude (X)"), max_digits=9, decimal_places=6, null=True, blank=True)
    primary_color = models.CharField(
        _("primary color"),
        max_length=7,
        blank=True,
        null=True,
        help_text=_("Primary theme color for the company's page (e.g., #0A3D62).")
    )
    secondary_color = models.CharField(
        _("secondary color"),
        max_length=7,
        blank=True,
        null=True,
        help_text=_("Secondary theme color for accents and links (e.g., #FF9F43).")
    )
    current_busy_level = models.PositiveIntegerField(
        choices=BusyLevel.choices,
        default=BusyLevel.AVERAGE,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text=_("Set your current production capacity (1=Fastest, 5=Slowest).")
    )
    services = models.ManyToManyField(
        ServiceCategory,
        blank=True,
        related_name='companies',
        verbose_name=_("services offered"),
        help_text=_("Select all the services this company provides.")
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Print Companies"
        ordering = ["name"]


    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        
        # Ensure the slug is unique upon creation
        if not self.pk:
            original_slug = self.slug
            counter = 1
            while PrintCompany.objects.filter(slug=self.slug).exists():
                self.slug = f'{original_slug}-{counter}'
                counter += 1
        super().save(*args, **kwargs)

    def get_busy_multiplier(self):
        """Converts the 1-5 busy level to a time multiplier for job estimates."""
        multipliers = {
            1: 0.6,  # 40% faster
            2: 0.8,  # 20% faster
            3: 1.0,  # Normal time
            4: 1.5,  # 50% slower
            5: 2.0,  # 100% slower
        }
        return Decimal(str(multipliers.get(self.current_busy_level, 1.0)))



class ClientProfile(models.Model):
    """
    Profile model for a client user.

    Extends the custom User model with client-specific information.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="client_profile",
        limit_choices_to={'user_type': User.UserType.CLIENT}
    )
    company_name = models.CharField(max_length=200, blank=True)
    billing_address = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "Client Profiles"
        
    def __str__(self):
        return self.user.get_full_name()


class CompanyStaffProfile(models.Model):
    """
    Profile model for staff members of a print company.

    Extends the custom User model with company-related information.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="staff_profile",
        limit_choices_to={'user_type__in': [
            User.UserType.COMPANY_OWNER,
            User.UserType.COMPANY_ADMIN,
            User.UserType.STAFF
        ]}
    )
    company = models.ForeignKey(
        PrintCompany,
        on_delete=models.CASCADE,
        related_name="staff_members"
    )
    job_title = models.CharField(max_length=100, blank=True)
    internal_notes = models.TextField(blank=True)

    class Meta:
        # Use a `UniqueConstraint` for modern Django versions (3.0+).
        constraints = [
            models.UniqueConstraint(fields=['user', 'company'], name='unique_staff_per_company')
        ]
        verbose_name_plural = "Company Staff Profiles"
        
    def __str__(self):
        return f"{self.user.get_full_name()} @ {self.company.name}"
    
    
class PortfolioItem(models.Model):
    """
    Represents a single piece of work in a company's portfolio.
    """
    company = models.ForeignKey(
        PrintCompany, 
        on_delete=models.CASCADE, 
        related_name='portfolio_items'
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='portfolio_images/')
    date_completed = models.DateField(null=True, blank=True)
    is_featured = models.BooleanField(
        default=False,
        help_text=_("Featured items may be displayed more prominently.")
    )

    class Meta:
        ordering = ['-date_completed']

    class Meta:
        verbose_name = _("Portfolio Item")
        verbose_name_plural = _("Portfolio Items")
        ordering = ['-date_completed']

    def __str__(self):
        return f"{self.title} for {self.company.name}"
    