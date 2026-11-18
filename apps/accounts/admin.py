"""Django admin registration — a developer convenience only (product admin panel is Docs-only)."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import EmailOTP, StudentProfile, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "full_name", "email", "role", "email_verified", "is_active")
    list_filter = ("role", "email_verified", "is_active", "is_staff")
    search_fields = ("username", "full_name", "email")
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Profile", {"fields": ("full_name", "email", "role", "email_verified", "created_by")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"fields": ("username", "full_name", "email", "role", "password1", "password2")}),
    )
    raw_id_fields = ("created_by",)


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "high_contrast", "large_text", "reduced_motion", "narration")
    search_fields = ("user__username", "user__full_name")


@admin.register(EmailOTP)
class EmailOTPAdmin(admin.ModelAdmin):
    list_display = ("user", "purpose", "created_at", "expires_at", "attempts", "used_at")
    readonly_fields = ("code_hash",)
