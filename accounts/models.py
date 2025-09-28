import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from typing import Optional, Any


class UserManager(BaseUserManager):
    """
    Custom user manager for Django's custom User model.

    This manager uses email as the unique identifier instead of a username.
    It provides helper methods for creating regular users and superusers.
    """
    def create_user(self, email: str, password: Optional[str] = None, **extra_fields: Any):
        """Creates and saves a new user with the given email and password."""
        if not email:
            raise ValueError(_("Email must be set"))
        
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: Optional[str] = None, **extra_fields: Any):
        """Creates and saves a new superuser with the given email and password."""
        # Set default values and validate them.
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError(_("Superuser must have is_staff=True."))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_("Superuser must have is_superuser=True."))

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom User model representing users of the application.

    Uses a UUID as the primary key and email as the unique username field.
    Includes different user types to handle various roles within the system.
    """
    class UserType(models.TextChoices):
        CLIENT = 'client', _('Client')
        COMPANY_OWNER = 'company_owner', _('Company Owner')
        COMPANY_ADMIN = 'company_admin', _('Company Admin')
        STAFF = 'staff', _('Staff')
        DESIGNER = 'designer', _('Designer')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(_('email address'), unique=True)
    first_name = models.CharField(_('first name'), max_length=150, blank=True)
    last_name = models.CharField(_('last name'), max_length=150, blank=True)
    
    # Permissions and status flags
    is_active = models.BooleanField(
        _('active'), 
        default=True,
        help_text=_('Designates whether this user should be treated as active. Unselect this instead of deleting accounts.'),
    )
    is_staff = models.BooleanField(
        _('staff status'),
        default=False,
        help_text=_('Designates whether the user can log into this admin site.'),
    )

    # Role
    user_type = models.CharField(
        _('user type'),
        max_length=20,
        choices=UserType.choices,
        default=UserType.CLIENT
    )

    # Optional profile info
    phone_number = models.CharField(_('phone number'), max_length=25, blank=True, null=True, help_text=_('Optional'))
    
    # Fields required for Django's auth system
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    
    # Custom manager
    objects = UserManager()

    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')
        # Add a unique constraint on email for an extra layer of database enforcement.
        constraints = [
            models.UniqueConstraint(fields=['email'], name='unique_user_email')
        ]

    def __str__(self):
        """Returns the email as the string representation."""
        return self.email

    def get_full_name(self):
        """Returns the full name, if available, otherwise a cleaned-up version."""
        return f"{self.first_name} {self.last_name}".strip() or self.email

    @property
    def is_client(self):
        """Returns True if the user is a client."""
        return self.user_type == self.UserType.CLIENT

    @property
    def is_company_staff(self):
        """Returns True if the user is part of a company's staff."""
        return self.user_type in [
            self.UserType.COMPANY_OWNER,
            self.UserType.COMPANY_ADMIN,
            self.UserType.STAFF
        ]
        
