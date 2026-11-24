"""Step 7: accessibility profile editor and how it's applied (A11Y-01..03)."""

import re
from pathlib import Path

import pytest
from django.urls import reverse

from apps.classrooms import services as classroom_services
from apps.classrooms.models import Enrollment, SessionParticipant
from apps.games import services as game_services
from apps.games.models import GameType

pytestmark = pytest.mark.django_db


def _body_classes(html: str) -> set[str]:
    return set(re.search(r'<body class="([^"]*)"', html).group(1).split())


def _set(student, **flags):
    profile = student.student_profile
    for k, v in flags.items():
        setattr(profile, k, v)
    profile.save()


def test_no_classes_by_default(student_client):
    html = student_client.get(reverse("play:join")).content.decode()
    assert not {c for c in _body_classes(html) if c.startswith("a11y-")}
    assert "data-reduced-motion" not in html


def test_profile_becomes_body_classes(student_client, student):
    _set(student, high_contrast=True, large_text=True, reduced_motion=True, keyboard_mode=True)
    html = student_client.get(reverse("play:join")).content.decode()
    assert {"a11y-contrast", "a11y-large-text", "a11y-reduced-motion", "a11y-keyboard"} <= (
        _body_classes(html)
    )
    assert 'data-reduced-motion="true"' in html  # splash.js skips the splash


def test_teachers_never_get_student_classes(teacher_client):
    html = teacher_client.get(reverse("teach:dashboard")).content.decode()
    assert not {c for c in _body_classes(html) if c.startswith("a11y-")}


def test_game_config_and_page_follow_profile(student_client, student, classroom):
    _set(student, reduced_motion=True, narration=True, keyboard_mode=True)
    session = classroom_services.start_session(classroom)
    classroom_services.join_session(student, session.code)
    participant = SessionParticipant.objects.get(session=session)
    round_ = game_services.start_round(
        participant, GameType.objects.get(key="fruit_blender"), "easy", "add"
    )
    assert round_.config_snapshot["a11y"] == {
        "reducedMotion": True,
        "narration": True,
        "keyboard": True,
    }
    html = student_client.get(reverse("games:round", args=[round_.pk])).content.decode()
    assert "keyboard-hint" in html and "a11y-keyboard" in _body_classes(html)


def test_reduced_motion_turns_off_video_autoplay(student_client, student, classroom):
    session = classroom_services.start_session(classroom)
    classroom_services.join_session(student, session.code)
    url = reverse("games:tutorial", args=[session.pk, "fruit_blender"])
    assert "autoplay" in student_client.get(url).content.decode()
    _set(student, reduced_motion=True)
    assert "autoplay" not in student_client.get(url).content.decode()


# --- Teacher editor (A11Y-01) ------------------------------------------------------------
def test_teacher_saves_profile(teacher_client, classroom, student):
    Enrollment.objects.create(classroom=classroom, student=student)
    url = reverse("teach:student_detail", args=[classroom.pk, student.pk])
    page = teacher_client.get(url).content.decode()
    assert "Accessibility" in page and "Standard settings" in page
    response = teacher_client.post(url, {"high_contrast": "on", "captions": "on"})
    assert response.url == url
    student.student_profile.refresh_from_db()
    p = student.student_profile
    assert (p.high_contrast, p.captions, p.large_text) == (True, True, False)
    page = teacher_client.get(url).content.decode()
    assert "High contrast" in page and "Standard settings" not in page


def test_unticking_turns_settings_off(teacher_client, classroom, student):
    Enrollment.objects.create(classroom=classroom, student=student)
    _set(student, high_contrast=True, large_text=True)
    teacher_client.post(reverse("teach:student_detail", args=[classroom.pk, student.pk]), {})
    student.student_profile.refresh_from_db()
    assert not student.student_profile.high_contrast and not student.student_profile.large_text


def test_other_teacher_cannot_change_profile(client, other_teacher, classroom, student):
    Enrollment.objects.create(classroom=classroom, student=student)
    client.force_login(other_teacher)
    url = reverse("teach:student_detail", args=[classroom.pk, student.pk])
    assert client.post(url, {"high_contrast": "on"}).status_code == 404
    student.student_profile.refresh_from_db()
    assert not student.student_profile.high_contrast


def test_contrast_mode_overrides_every_colour_token():
    """Every colour token in tokens.css must be redefined for high contrast."""
    from django.contrib.staticfiles import finders

    tokens = Path(finders.find("css/tokens.css")).read_text(encoding="utf-8")
    a11y = Path(finders.find("css/a11y.css")).read_text(encoding="utf-8")
    contrast_block = re.search(r"\.a11y-contrast \{(.*?)\}", a11y, re.S).group(1)
    colour_tokens = set(re.findall(r"(--color-[\w-]+):", tokens))
    overridden = set(re.findall(r"(--color-[\w-]+):", contrast_block))
    assert colour_tokens - overridden == set()
