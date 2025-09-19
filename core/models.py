import uuid
from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from accounts.models import User


class PrintCompany(models.Model):
    """Model representing a print company."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_("Company Name"), max_length=255, unique=True)
    slug = models.SlugField(max_length=255, unique=True, blank=True, db_index=True)
    description = models.TextField(blank=True, null=True)
    logo = models.ImageField(upload_to="company_logos/", blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    address = models.CharField(max_length=255, blank=True, null=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Print Companies"

    def save(self, *args, **kwargs):
        """Automatically generates a slug from the company name."""
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


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
    