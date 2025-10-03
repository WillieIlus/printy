#accounts/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import User, ClientProfile, CompanyStaffProfile # Assuming these models are correct



class CustomUserCreationForm(UserCreationForm):
    """
    A custom form for creating new users in the admin,
    based on UserCreationForm but using email as the unique identifier.
    """
    class Meta:
        model = User
        fields = ("email", "user_type") # Explicitly define fields for creation

    def clean_email(self):
        email = self.cleaned_data.get('email')
        # Ensure email is unique during creation
        if User.objects.filter(email=email).exists():
            # Use self._meta.model._meta.verbose_name.capitalize() if available
            raise forms.ValidationError(_("A user with that email already exists.")) 
        return email

    def save(self, commit=True):
        # The parent save method calls create_user() on the manager
        user = super().save(commit=False)
        # Set the user type if it was not handled by the super() call
        if 'user_type' in self.cleaned_data:
            user.user_type = self.cleaned_data['user_type']
        
        if commit:
            user.save()
        return user


# (Optional: Define a CustomUserChangeForm if you need more custom validation 
# on the change form, but often BaseUserAdmin's setup is sufficient if fieldsets are defined.)
class CustomUserChangeForm(UserChangeForm):
    """A custom form for editing users."""
    class Meta:
        model = User
        fields = '__all__'

# Inline for ClientProfile within User admin
class ClientProfileInline(admin.StackedInline):
    model = ClientProfile
    can_delete = False
    verbose_name_plural = 'client profile'
    fieldsets = (
        (None, {
            'fields': ('company_name',),
            'description': 'Client-specific information. Only for users with "Client" user type.'
        }),
    )

# Inline for CompanyStaffProfile within User admin
class CompanyStaffProfileInline(admin.StackedInline):
    model = CompanyStaffProfile
    can_delete = False
    verbose_name_plural = 'company staff profile'
    raw_id_fields = ('company',) # Use raw_id_fields for company to avoid large dropdowns
    fieldsets = (
        (None, {
            'fields': ('company',),
            'description': 'Company-specific information. For users with "Company Owner", "Company Admin", or "Staff" user types.'
        }),
    )

# ---

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Custom admin panel configuration for the User model."""

    # Assign the custom forms
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm # Use the custom change form (optional, but good practice)

    # Fields shown in the list view
    list_display = ("email", "first_name", "last_name", "user_type", "is_staff", "is_active")
    list_filter = ("user_type", "is_staff", "is_active", "is_superuser")
    ordering = ("email",)
    
    # Corrected and singular search fields definition
    search_fields = ("email", "first_name", "last_name", "phone_number") 

    inlines = [ClientProfileInline, CompanyStaffProfileInline]

    def get_inline_instances(self, request, obj=None):
        """Conditionally show inlines based on user_type."""
        if obj is None: # For "Add User" page, don't show inlines until user is saved
            return []
        
        inlines = []
        for inline_class in self.inlines:
            # Check if the user is a client and should see the ClientProfileInline
            if inline_class is ClientProfileInline and obj.is_client:
                inlines.append(inline_class(self.model, self.admin_site))
            # Check if the user is company staff and should see the CompanyStaffProfileInline
            elif inline_class is CompanyStaffProfileInline and obj.is_company_staff:
                inlines.append(inline_class(self.model, self.admin_site))
        return inlines
      
    
    # Organize fields into sections in the admin detail view (for editing)
    # Note: Using BaseUserAdmin's structure but replacing 'username' with 'email'
    fieldsets = (
        (None, {"fields": ("email", "password")}), # Use 'email' as the main field
        (_("Personal info"), {"fields": ("first_name", "last_name", "phone_number", "user_type")}),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}), # Added date_joined which is in AbstractUser
    )

    # Fields shown when adding a new user via the admin (defined by CustomUserCreationForm)
    # The fields tuple in add_fieldsets should map to the fields in CustomUserCreationForm
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "password", "password2", "user_type", "first_name", "last_name", "is_staff"),
            },
        ),
    )
    
    # Fields shown only when editing (detail view), not creating
    # readonly_fields = ('last_login', 'date_joined',)


@admin.register(ClientProfile)
class ClientProfileAdmin(admin.ModelAdmin):
    autocomplete_fields = ('user',)
    list_display = ('user', 'get_user_email', 'company_name')
    list_select_related = ('user',)
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'company_name')

    @admin.display(description='User Email', ordering='user__email')
    def get_user_email(self, obj):
        return obj.user.email

@admin.register(CompanyStaffProfile)
class CompanyStaffProfileAdmin(admin.ModelAdmin):
    autocomplete_fields = ('user', 'company')
    list_display = ('user', 'company', 'job_title')
    list_select_related = ('user', 'company')
    list_filter = ('company',)
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'company__name', 'job_title')