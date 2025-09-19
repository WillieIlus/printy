# from django.contrib import admin
# from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
# from django.utils.translation import gettext_lazy as _

# # Make sure to import your User model correctly
# from .models import User


# @admin.register(User)
# class UserAdmin(BaseUserAdmin):
#     """Custom admin panel configuration for the User model."""

#     # Fields shown in the list view of users
#     list_display = ("email", "first_name", "last_name", "user_type", "is_staff", "is_active")
#     list_filter = ("user_type", "is_staff", "is_active", "is_superuser")
#     search_fields = ("email", "first_name", "last_name")
#     ordering = ("email",)

#     # Organizes fields into sections on the user *edit* page
#     fieldsets = (
#         (None, {"fields": ("email", "password")}),
#         (_("Personal info"), {"fields": ("first_name", "last_name", "phone_number")}),
#         (_("Role"), {"fields": ("user_type",)}),
#         (
#             _("Permissions"),
#             {
#                 "fields": (
#                     "is_active",
#                     "is_staff",
#                     "is_superuser",
#                     "groups",
#                     "user_permissions",
#                 ),
#             },
#         ),
#         (_("Important dates"), {"fields": ("last_login",)}),
#     )

#     # Organizes fields on the user *creation* page
#     add_fieldsets = (
#         (
#             None,
#             {
#                 "classes": ("wide",),
#                 # Added first/last name and corrected 'password1' to 'password'
#                 "fields": ("email", "password", "password2", "first_name", "last_name", "user_type"),
#             },
#         ),
#     )

#     # Specifies fields that cannot be edited
#     readonly_fields = ('last_login',)