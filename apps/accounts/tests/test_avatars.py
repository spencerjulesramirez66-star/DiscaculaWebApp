"""Step 5: avatar packs and builder (STU-01/02)."""

import pytest
from django.urls import reverse

from apps.accounts import avatars

pytestmark = pytest.mark.django_db


def test_default_avatar_fills_required_layers_only():
    default = avatars.default_avatar()
    assert default["pack"] == "default"
    assert default["base"] == "cat" and default["color"] == "orange"
    assert default["hat"] == avatars.NONE


def test_clean_avatar_drops_invalid_choices():
    cleaned = avatars.clean_avatar({"base": "dragon", "hat": "crown", "evil": "<script>"})
    assert cleaned["base"] == "cat"  # invalid → default
    assert cleaned["hat"] == "crown"
    assert "evil" not in cleaned


def test_required_layer_cannot_be_none():
    assert avatars.clean_avatar({"base": avatars.NONE})["base"] == "cat"


def test_render_parts_inlines_svg_and_applies_colour():
    parts = avatars.render_parts({"base": "bear", "color": "blue", "hat": "crown"})
    assert parts["color"] == "#64b5f6"
    assert parts["label"] == "Bear"
    assert len(parts["layers"]) == 2 and all("<svg" in layer for layer in parts["layers"])


def test_builder_saves_and_redirects_to_next(student_client, student):
    url = reverse("accounts:avatar")
    page = student_client.get(url + "?next=/play/").content.decode()
    assert "Make your character!" in page and "<svg" in page
    response = student_client.post(
        url, {"base": "bear", "color": "green", "hair": "none", "hat": "crown", "next": "/play/"}
    )
    assert response.url == "/play/"
    student.student_profile.refresh_from_db()
    assert student.student_profile.avatar["base"] == "bear"
    assert student.student_profile.avatar["hat"] == "crown"


def test_builder_ignores_offsite_next(student_client):
    response = student_client.post(
        reverse("accounts:avatar"), {"base": "cat", "next": "https://evil.example/"}
    )
    assert response.url == reverse("play:join")


def test_builder_is_students_only(teacher_client):
    assert teacher_client.get(reverse("accounts:avatar")).status_code == 403


def test_header_shows_student_avatar(student_client, student):
    student.student_profile.avatar = {"base": "bear", "color": "blue"}
    student.student_profile.save()
    html = student_client.get(reverse("play:join")).content.decode()
    assert 'class="avatar avatar--sm"' in html and "#64b5f6" in html
