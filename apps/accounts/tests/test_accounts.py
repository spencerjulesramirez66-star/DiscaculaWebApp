import re
from datetime import timedelta

import pytest
from django.contrib.auth import authenticate
from django.core import mail
from django.db import IntegrityError
from django.urls import reverse
from django.utils import timezone

from apps.accounts import services
from apps.accounts.models import EmailOTP, OTPPurpose, Role, User
from conftest import PASSWORD

pytestmark = pytest.mark.django_db


def _code_from_last_email() -> str:
    return re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)


# --- Models & credentials ---------------------------------------------------
def test_teacher_email_unique_case_insensitive(teacher):
    with pytest.raises(IntegrityError):
        User.objects.create(username="x", email="ANA@school.test", role=Role.TEACHER)


def test_students_may_share_a_parent_email(db):
    a = services.create_student(full_name="Kid A", password=PASSWORD, email="mom@home.test")
    b = services.create_student(full_name="Kid B", password=PASSWORD, email="mom@home.test")
    assert a.email == b.email


def test_suggest_username_numbers_duplicates(db):
    assert services.suggest_username("Maria Santos") == "maria.s"
    services.create_student(full_name="Maria Santos", password=PASSWORD)
    assert services.suggest_username("Maria Sison") == "maria.s2"
    assert services.suggest_username("Pía") == "pia"


def test_kid_password_format():
    assert re.fullmatch(r"[a-z]+-[a-z]+-\d{2}", services.generate_kid_password())


def test_create_student_makes_profile(student):
    assert student.student_profile.has_avatar is False


# --- Login -------------------------------------------------------------------
def test_teacher_logs_in_with_email_student_with_username(teacher, student):
    assert authenticate(username="ANA@school.test", password=PASSWORD) == teacher
    assert authenticate(username="Maria", password=PASSWORD) == student
    assert authenticate(username="maria", password="wrong") is None
    assert authenticate(username="nobody", password=PASSWORD) is None


def test_student_email_is_not_a_login(db):
    services.create_student(full_name="Kid", username="kid", password=PASSWORD, email="p@x.test")
    assert authenticate(username="p@x.test", password=PASSWORD) is None


def test_remember_me_off_ends_with_browser(client, student):
    client.post(reverse("accounts:login"), {"username": "maria", "password": PASSWORD})
    assert client.session.get_expire_at_browser_close() is True


def test_remember_me_on_keeps_login(client, student):
    client.post(
        reverse("accounts:login"),
        {"username": "maria", "password": PASSWORD, "remember_me": "on"},
    )
    assert client.session.get_expire_at_browser_close() is False


def test_after_login_routes_by_role(client, teacher, student):
    client.force_login(student)
    assert client.get(reverse("accounts:after_login")).url == reverse("play:join")
    client.force_login(teacher)
    assert client.get(reverse("accounts:after_login")).url == reverse("teach:dashboard")


# --- Teacher signup + email OTP ------------------------------------------------
def test_teacher_signup_sends_code_and_verifies(client):
    response = client.post(
        reverse("accounts:signup_teacher"),
        {
            "full_name": "Carla Lim",
            "email": "Carla@School.test",
            "password1": PASSWORD,
            "password2": PASSWORD,
        },
    )
    assert response.url == reverse("accounts:verify_email")
    user = User.objects.get(email="carla@school.test")
    assert user.is_teacher and not user.email_verified
    assert len(mail.outbox) == 1

    # Unverified teachers can't reach the dashboard.
    assert client.get(reverse("teach:dashboard")).url == reverse("accounts:verify_email")

    client.post(reverse("accounts:verify_email"), {"code": _code_from_last_email()})
    user.refresh_from_db()
    assert user.email_verified
    assert client.get(reverse("teach:dashboard")).status_code == 200


def test_duplicate_teacher_email_rejected(client, teacher):
    response = client.post(
        reverse("accounts:signup_teacher"),
        {
            "full_name": "X",
            "email": "ana@school.test",
            "password1": PASSWORD,
            "password2": PASSWORD,
        },
    )
    assert response.status_code == 200
    assert "already exists" in response.content.decode()


def test_otp_wrong_code_counts_attempts_then_locks(teacher):
    services.issue_otp(teacher, OTPPurpose.VERIFY_EMAIL)
    real = _code_from_last_email()
    wrong = "000000" if real != "000000" else "111111"
    for _ in range(5):
        with pytest.raises(services.OTPError):
            services.check_otp(teacher, OTPPurpose.VERIFY_EMAIL, wrong)
    with pytest.raises(services.OTPError, match="Too many"):
        services.check_otp(teacher, OTPPurpose.VERIFY_EMAIL, real)


def test_otp_expires(teacher):
    services.issue_otp(teacher, OTPPurpose.VERIFY_EMAIL)
    EmailOTP.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
    with pytest.raises(services.OTPError, match="expired"):
        services.check_otp(teacher, OTPPurpose.VERIFY_EMAIL, _code_from_last_email())


def test_otp_single_use_and_stored_hashed(teacher):
    services.issue_otp(teacher, OTPPurpose.VERIFY_EMAIL)
    code = _code_from_last_email()
    assert code not in EmailOTP.objects.get().code_hash
    services.check_otp(teacher, OTPPurpose.VERIFY_EMAIL, code)
    with pytest.raises(services.OTPError):
        services.check_otp(teacher, OTPPurpose.VERIFY_EMAIL, code)


def test_resend_has_cooldown_and_invalidates_old_code(teacher):
    services.issue_otp(teacher, OTPPurpose.VERIFY_EMAIL)
    first = _code_from_last_email()
    with pytest.raises(services.OTPError, match="wait"):
        services.issue_otp(teacher, OTPPurpose.VERIFY_EMAIL)
    EmailOTP.objects.update(created_at=timezone.now() - timedelta(minutes=2))
    services.issue_otp(teacher, OTPPurpose.VERIFY_EMAIL)
    second = _code_from_last_email()
    if first != second:
        with pytest.raises(services.OTPError):
            services.check_otp(teacher, OTPPurpose.VERIFY_EMAIL, first)
    services.check_otp(teacher, OTPPurpose.VERIFY_EMAIL, second)


# --- Student signup ------------------------------------------------------------
def test_student_signup_logs_in_and_goes_to_room_code(client):
    response = client.post(
        reverse("accounts:signup_student"),
        {
            "full_name": "Leo Tan",
            "username": "leo",
            "password1": PASSWORD,
            "password2": PASSWORD,
            "email": "",
        },
    )
    assert response.url == reverse("accounts:after_login")
    assert User.objects.get(username="leo").is_student
    assert client.get(reverse("play:join")).status_code == 200


def test_student_username_taken_case_insensitive(client, student):
    response = client.post(
        reverse("accounts:signup_student"),
        {"full_name": "M", "username": "MARIA", "password1": PASSWORD, "password2": PASSWORD},
    )
    assert "taken" in response.content.decode()


def test_student_username_rejects_at_sign(client):
    response = client.post(
        reverse("accounts:signup_student"),
        {"full_name": "M", "username": "m@x", "password1": PASSWORD, "password2": PASSWORD},
    )
    assert not User.objects.filter(username="m@x").exists()
    assert response.status_code == 200


# --- Forgot password -------------------------------------------------------------
def test_forgot_password_with_email_resets(client, db):
    services.create_student(
        full_name="Kid", username="kid", password=PASSWORD, email="parent@home.test"
    )
    client.post(reverse("accounts:forgot_password"), {"identifier": "kid"})
    assert mail.outbox[-1].to == ["parent@home.test"]
    new = "green-fox-77-ok"
    response = client.post(
        reverse("accounts:reset_password"),
        {"code": _code_from_last_email(), "password1": new, "password2": new},
    )
    assert response.url == reverse("accounts:login")
    assert authenticate(username="kid", password=new)


def test_forgot_password_without_email_sends_nothing_and_reveals_nothing(client, student):
    response = client.post(reverse("accounts:forgot_password"), {"identifier": "maria"})
    assert response.url == reverse("accounts:reset_password")
    assert mail.outbox == []
    unknown = client.post(reverse("accounts:forgot_password"), {"identifier": "ghost"})
    assert unknown.url == response.url  # same response for unknown accounts


def test_reset_page_requires_forgot_step(client):
    assert client.get(reverse("accounts:reset_password")).url == reverse("accounts:forgot_password")


def test_signup_survives_email_failure(client):
    """Wrong Gmail settings / no internet: friendly message, no crash, account still created."""
    import smtplib
    from unittest import mock

    boom = smtplib.SMTPServerDisconnected("Connection unexpectedly closed")
    with mock.patch("apps.accounts.services.send_mail", side_effect=boom):
        response = client.post(
            reverse("accounts:signup_teacher"),
            {
                "full_name": "Dina Cruz",
                "email": "dina@school.test",
                "password1": PASSWORD,
                "password2": PASSWORD,
            },
            follow=True,
        )
    assert response.status_code == 200
    assert "couldn&#x27;t send the email" in response.content.decode()
    user = User.objects.get(email="dina@school.test")
    assert not user.otps.exists()  # the unsent code was rolled back
    # Resend works once email is fixed (cooldown doesn't block: nothing was sent).
    client.post(reverse("accounts:resend_verification"))
    assert user.otps.count() == 1 and len(mail.outbox) == 1


def test_forgot_password_survives_email_failure(client):
    from unittest import mock

    services.create_student(full_name="Kid", username="kid", password=PASSWORD, email="p@x.test")
    with mock.patch("apps.accounts.services.send_mail", side_effect=OSError("network down")):
        response = client.post(reverse("accounts:forgot_password"), {"identifier": "kid"})
    assert response.status_code == 302  # same neutral response, no crash
