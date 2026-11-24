"""Presentation prep: demo command, star result screen, hosting settings."""

import importlib
import os
import subprocess
import sys
from io import StringIO

import pytest
from django.contrib.auth import authenticate
from django.core.management import CommandError, call_command
from django.urls import reverse

from apps.accounts import services as account_services
from apps.accounts.models import User
from apps.classrooms.models import ClassSession
from apps.games.models import GameRound, QuestionSet
from conftest import PASSWORD

pytestmark = pytest.mark.django_db


def _demo():
    out = StringIO()
    call_command("demo", stdout=out)
    return out.getvalue()


def test_demo_creates_working_logins_and_history():
    output = _demo()
    assert "teacher@demo.school" in output and "apple-123" in output
    teacher = authenticate(username="teacher@demo.school", password="blender-123")
    assert teacher and teacher.email_verified
    for name in ["maria", "juan", "ana", "leo"]:
        assert authenticate(username=name, password="apple-123")
    ana = User.objects.get(username="ana").student_profile
    assert ana.high_contrast and ana.large_text
    leo = User.objects.get(username="leo")
    assert not leo.student_profile.has_avatar and not leo.game_rounds.exists()
    assert GameRound.objects.filter(completed_at__isnull=False).count() == 5
    # Class time from "yesterday" is over, so today's starts fresh.
    assert not ClassSession.objects.filter(status="open").exists()
    assert QuestionSet.objects.filter(owner=teacher).count() == 1


def test_demo_can_run_again_without_duplicates():
    _demo()
    _demo()
    assert User.objects.filter(email="teacher@demo.school").count() == 1
    assert User.objects.filter(username="maria").count() == 1
    assert GameRound.objects.count() == 5


def test_demo_leaves_other_accounts_alone(teacher):
    # (The shared `student` fixture is called "maria", which the demo rightly refuses to touch.)
    other = account_services.create_student(full_name="Pia", username="pia", password=PASSWORD)
    _demo()
    _demo()
    assert User.objects.filter(pk__in=[teacher.pk, other.pk]).count() == 2


def test_demo_refuses_to_overwrite_a_real_account():
    account_services.create_student(full_name="Real Maria", username="maria", password=PASSWORD)
    with pytest.raises(CommandError, match="maria"):
        _demo()
    assert User.objects.get(username="maria").full_name == "Real Maria"


def test_result_shows_stars_not_percent_to_students(client):
    _demo()
    maria = User.objects.get(username="maria")
    client.force_login(maria)
    round_ = GameRound.objects.filter(student=maria, score_percent=60).get()
    html = client.get(reverse("games:result", args=[round_.pk])).content.decode()
    assert "3 out of 5 right the first time" in html
    assert html.count("result__star--empty") == 2
    assert "60%" not in html


def test_prod_settings_load_and_add_render_host():
    """Import prod settings in a clean process with Render-like environment variables."""
    env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "config.settings.prod",
        "SECRET_KEY": "x" * 50,
        "RENDER_EXTERNAL_HOSTNAME": "my-app.onrender.com",
        "DATABASE_URL": "sqlite:///:memory:",
    }
    code = (
        "import django; django.setup(); from django.conf import settings as s; "
        "assert not s.DEBUG; assert 'my-app.onrender.com' in s.ALLOWED_HOSTS; "
        "assert 'https://my-app.onrender.com' in s.CSRF_TRUSTED_ORIGINS; "
        "assert 'whitenoise.middleware.WhiteNoiseMiddleware' == s.MIDDLEWARE[1]; "
        "assert 'debug_toolbar' not in s.INSTALLED_APPS; print('ok')"
    )
    result = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


def test_dev_settings_accept_tunnel_addresses():
    dev = importlib.import_module("config.settings.dev")
    assert ".ngrok-free.app" in dev.ALLOWED_HOSTS and ".trycloudflare.com" in dev.ALLOWED_HOSTS
    assert "https://*.ngrok-free.app" in dev.CSRF_TRUSTED_ORIGINS


def test_login_works_through_an_ngrok_link():
    """A real browser on https://<name>.ngrok-free.dev posts the login form through the tunnel."""
    from django.test import Client, override_settings

    dev = importlib.import_module("config.settings.dev")  # the settings runserver uses
    _demo()
    browser = Client(enforce_csrf_checks=True)
    host = "demo-class.ngrok-free.dev"
    with override_settings(
        ALLOWED_HOSTS=dev.ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS=dev.CSRF_TRUSTED_ORIGINS
    ):
        page = browser.get(reverse("accounts:login"), HTTP_HOST=host)
        assert page.status_code == 200
        token = page.cookies["csrftoken"].value
        response = browser.post(
            reverse("accounts:login"),
            {"username": "maria", "password": "apple-123", "csrfmiddlewaretoken": token},
            HTTP_HOST=host,
            HTTP_ORIGIN=f"https://{host}",
        )
    assert response.status_code == 302, "login was refused (CSRF / host)"
