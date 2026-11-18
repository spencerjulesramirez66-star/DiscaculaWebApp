"""Account business rules. Views call these; tests exercise them directly."""

import secrets
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from django.utils.text import slugify

from .models import EmailOTP, OTPPurpose, Role, StudentProfile, User

# ---------------------------------------------------------------------------
# Readable credentials for kids (ACC-05)
# ---------------------------------------------------------------------------
_COLORS = ["red", "blue", "green", "pink", "gold", "teal", "lime", "plum", "sky", "sun"]
_ANIMALS = ["cat", "dog", "fox", "owl", "bee", "cow", "pig", "hen", "elk", "yak", "ant", "bat"]


def generate_kid_password() -> str:
    """e.g. 'red-fox-42': easy to read aloud and type."""
    return f"{secrets.choice(_COLORS)}-{secrets.choice(_ANIMALS)}-{secrets.randbelow(90) + 10}"


def suggest_username(full_name: str) -> str:
    """'Maria Santos' → 'maria.s', then 'maria.s2', 'maria.s3' … if taken."""
    parts = [slugify(p).replace("-", "") for p in full_name.split()]
    parts = [p for p in parts if p] or ["student"]
    base = parts[0] if len(parts) == 1 else f"{parts[0]}.{parts[-1][0]}"
    base = base[:140]
    candidate, n = base, 1
    while User.objects.filter(username__iexact=candidate).exists():
        n += 1
        candidate = f"{base}{n}"
    return candidate


# ---------------------------------------------------------------------------
# Account creation
# ---------------------------------------------------------------------------
def _teacher_username(email: str) -> str:
    # Teachers never see or use their username; it only has to be unique.
    local = slugify(email.split("@")[0]).replace("-", "") or "teacher"
    return f"t.{local[:40]}.{secrets.token_hex(3)}"


@transaction.atomic
def create_teacher(*, full_name: str, email: str, password: str) -> User:
    user = User(
        username=_teacher_username(email),
        email=email.strip().lower(),
        full_name=full_name.strip(),
        role=Role.TEACHER,
    )
    user.set_password(password)
    user.save()
    return user


@transaction.atomic
def create_student(
    *,
    full_name: str,
    password: str,
    username: str | None = None,
    email: str = "",
    created_by: User | None = None,
) -> User:
    user = User(
        username=username or suggest_username(full_name),
        email=(email or "").strip().lower(),
        full_name=full_name.strip(),
        role=Role.STUDENT,
        created_by=created_by,
    )
    user.set_password(password)
    user.save()
    StudentProfile.objects.create(user=user)
    return user


def set_new_kid_password(student: User) -> str:
    """Give a student a fresh readable password and return it (shown to the teacher once).

    Permission checks live with the caller (classrooms.services), which knows
    which students belong to which teacher.
    """
    new_password = generate_kid_password()
    student.set_password(new_password)
    student.save(update_fields=["password"])
    return new_password


# ---------------------------------------------------------------------------
# One-time codes (ACC-02, ACC-08)
# ---------------------------------------------------------------------------
class OTPError(Exception):
    """Raised with a user-facing message."""


def _hash_code(user: User, purpose: str, code: str) -> str:
    return salted_hmac(
        "accounts.otp", f"{user.pk}:{purpose}:{code}", algorithm="sha256"
    ).hexdigest()


def seconds_until_resend(user: User, purpose: str) -> int:
    latest = user.otps.filter(purpose=purpose).order_by("-created_at").first()
    if not latest:
        return 0
    ready_at = latest.created_at + timedelta(seconds=settings.OTP_RESEND_COOLDOWN_SECONDS)
    return max(0, int((ready_at - timezone.now()).total_seconds()))


@transaction.atomic
def issue_otp(user: User, purpose: str) -> None:
    """Create a fresh code, invalidate older unused ones, and email it."""
    if wait := seconds_until_resend(user, purpose):
        raise OTPError(f"Please wait {wait} seconds before asking for a new code.")
    if not user.email:
        raise OTPError("This account has no email address.")

    user.otps.filter(purpose=purpose, used_at__isnull=True).update(used_at=timezone.now())
    code = f"{secrets.randbelow(1_000_000):06d}"
    EmailOTP.objects.create(
        user=user,
        purpose=purpose,
        code_hash=_hash_code(user, purpose, code),
        expires_at=timezone.now() + timedelta(minutes=settings.OTP_TTL_MINUTES),
    )
    context = {
        "user": user,
        "code": code,
        "minutes": settings.OTP_TTL_MINUTES,
        "SITE_NAME": settings.SITE_NAME,
        "is_verify": purpose == OTPPurpose.VERIFY_EMAIL,
    }
    what = "verification" if context["is_verify"] else "password reset"
    send_mail(
        f"{settings.SITE_NAME}: your {what} code",
        render_to_string("accounts/email/otp.txt", context),
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
    )


def check_otp(user: User, purpose: str, code: str) -> None:
    """Consume a valid code or raise OTPError. Limits attempts per code."""
    otp = user.otps.filter(purpose=purpose, used_at__isnull=True).order_by("-created_at").first()
    if otp is None:
        raise OTPError("No active code. Please ask for a new one.")
    if otp.is_expired:
        raise OTPError("That code has expired. Please ask for a new one.")
    if otp.attempts >= settings.OTP_MAX_ATTEMPTS:
        raise OTPError("Too many tries. Please ask for a new code.")

    otp.attempts += 1
    if not constant_time_compare(otp.code_hash, _hash_code(user, purpose, code.strip())):
        otp.save(update_fields=["attempts", "updated_at"])
        left = settings.OTP_MAX_ATTEMPTS - otp.attempts
        if left:
            raise OTPError(f"That code is not right. {left} tries left.")
        raise OTPError("Too many tries. Please ask for a new code.")
    otp.used_at = timezone.now()
    otp.save(update_fields=["attempts", "used_at", "updated_at"])


def verify_email(user: User, code: str) -> None:
    check_otp(user, OTPPurpose.VERIFY_EMAIL, code)
    user.email_verified = True
    user.save(update_fields=["email_verified"])


def find_user_for_reset(identifier: str) -> User | None:
    """Username (students) or email (teachers). The UI never reveals whether it matched."""
    identifier = identifier.strip()
    if "@" in identifier:
        return User.objects.filter(email__iexact=identifier, role=Role.TEACHER).first()
    return User.objects.filter(username__iexact=identifier).first()
