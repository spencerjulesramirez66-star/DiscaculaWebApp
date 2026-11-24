"""Accounts: one User model for teachers and students (ADR-0004). See docs/04-data-model.md."""

from django.contrib.auth.models import AbstractUser, UserManager
from django.core.validators import RegexValidator
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel

# Students log in with a username; teachers with an email. Keeping "@" out of
# usernames lets one login box tell the two apart.
username_validator = RegexValidator(
    r"^[a-zA-Z0-9._-]+$",
    _("Use letters and numbers only, with no spaces."),
)


class Role(models.TextChoices):
    TEACHER = "teacher", _("Teacher")
    STUDENT = "student", _("Student")


class AppUserManager(UserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        # Superusers (you, for /admin during dev) act as verified teachers.
        extra_fields.setdefault("role", Role.TEACHER)
        extra_fields.setdefault("email_verified", True)
        extra_fields.setdefault("full_name", username)
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):
    username = models.CharField(
        _("username"),
        max_length=150,
        unique=True,
        validators=[username_validator],
        error_messages={"unique": _("That username is taken.")},
    )
    full_name = models.CharField(_("full name"), max_length=150)
    role = models.CharField(max_length=16, choices=Role.choices)
    email_verified = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_students",
        help_text=_("Teacher who created this student account, if any."),
    )

    objects = AppUserManager()

    REQUIRED_FIELDS = ["email", "full_name"]

    class Meta:
        constraints = [
            # Teacher emails are logins → unique. Student emails may be shared
            # (siblings with one parent email), so they are not constrained.
            models.UniqueConstraint(
                Lower("email"),
                condition=models.Q(role="teacher"),
                name="unique_teacher_email",
            ),
        ]

    def __str__(self):
        return self.display_name

    @property
    def display_name(self) -> str:
        return self.full_name or self.username

    @property
    def is_teacher(self) -> bool:
        return self.role == Role.TEACHER

    @property
    def is_student(self) -> bool:
        return self.role == Role.STUDENT


def default_avatar() -> dict:
    return {}


class StudentProfile(TimeStampedModel):
    """Student-only data: avatar + accessibility profile (docs/06-accessibility.md)."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="student_profile")
    avatar = models.JSONField(default=default_avatar, blank=True)

    narration = models.BooleanField(default=False)
    captions = models.BooleanField(default=False)
    high_contrast = models.BooleanField(default=False)
    large_text = models.BooleanField(default=False)
    reduced_motion = models.BooleanField(default=False)
    keyboard_mode = models.BooleanField(default=False)

    def __str__(self):
        return f"Profile of {self.user}"

    @property
    def has_avatar(self) -> bool:
        return bool(self.avatar)


class OTPPurpose(models.TextChoices):
    VERIFY_EMAIL = "verify_email", _("Verify email")
    RESET_PASSWORD = "reset_password", _("Reset password")


class EmailOTP(TimeStampedModel):
    """A one-time 6-digit code sent by email. Only a hash of the code is stored."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="otps")
    purpose = models.CharField(max_length=32, choices=OTPPurpose.choices)
    code_hash = models.CharField(max_length=128)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["user", "purpose", "-created_at"])]

    def __str__(self):
        return f"OTP({self.purpose}) for {self.user}"

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at
