"""Step 5: tutorial gate (GAM-09) and teacher video upload (CON-04/05)."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse

from apps.classrooms import services as classroom_services
from apps.content import services
from apps.content.models import TutorialView, Video
from apps.games.models import ClassroomGameConfig, GameType

pytestmark = pytest.mark.django_db


@pytest.fixture
def fruit_blender():
    return GameType.objects.get(key="fruit_blender")


@pytest.fixture
def joined(classroom, student):
    session = classroom_services.start_session(classroom)
    classroom_services.join_session(student, session.code)
    return session


def _mp4(name="lesson.mp4", size=1024):
    return SimpleUploadedFile(name, b"\x00" * size, content_type="video/mp4")


def _vtt(body=b"WEBVTT\n\n00:00.000 --> 00:01.000\nHi\n", name="lesson.vtt"):
    return SimpleUploadedFile(name, body, content_type="text/vtt")


# --- Tutorial gate -----------------------------------------------------------------------
def test_default_video_seeded(fruit_blender):
    video = services.default_video(fruit_blender)
    assert video and video.is_default and video.static_path.endswith(".webm")
    assert video.captions_url.endswith(".vtt")


def test_first_play_requires_tutorial_then_not_again(
    student_client, student, joined, fruit_blender
):
    start = reverse("games:start", args=[joined.pk, "fruit_blender"])
    tutorial = reverse("games:tutorial", args=[joined.pk, "fruit_blender"])
    assert student_client.get(start).url == tutorial
    page = student_client.get(tutorial).content.decode()
    assert "How to play Fruit Blender" in page
    student_client.post(tutorial)
    assert TutorialView.objects.get(student=student, game_type=fruit_blender).completed
    assert student_client.get(start).status_code == 200
    # "Watch again" still works and the Done button is no longer locked.
    again = student_client.get(tutorial).content.decode()
    assert (
        "data-tutorial-done" in again
        and "disabled" not in again.split("data-tutorial-done")[1][:40]
    )


def test_missing_video_file_falls_back_to_written_steps(student_client, joined, fruit_blender):
    Video.objects.filter(owner__isnull=True).update(static_path="assets/videos/missing.webm")
    page = student_client.get(reverse("games:tutorial", args=[joined.pk, "fruit_blender"]))
    html = page.content.decode()
    assert "<video" not in html and "Press Blend!" in html
    # Never stuck: the ready button isn't locked when there's no video.
    assert "disabled" not in html.split("data-tutorial-done")[1][:40]


def test_classroom_video_overrides_default(teacher, classroom, fruit_blender):
    mine = Video.objects.create(owner=teacher, game_type=fruit_blender, title="Mine", file=_mp4())
    ClassroomGameConfig.objects.create(classroom=classroom, game_type=fruit_blender, video=mine)
    assert services.tutorial_video(fruit_blender, classroom) == mine
    assert services.tutorial_video(fruit_blender, None).is_default


def test_captions_on_by_default_when_profile_asks(student_client, student, joined):
    student.student_profile.captions = True
    student.student_profile.save()
    # Default placeholder may be missing in a fresh checkout; give it a real file for this test.
    Video.objects.filter(owner__isnull=True).update(static_path="assets/branding/logo.svg")
    html = student_client.get(reverse("games:tutorial", args=[joined.pk, "fruit_blender"]))
    html = html.content.decode()
    assert 'kind="captions"' in html and "default" in html.split('kind="captions"')[1][:200]


# --- Video upload ----------------------------------------------------------------------------
def test_upload_video_with_captions(teacher_client, teacher, fruit_blender):
    response = teacher_client.post(
        reverse("videos:upload"),
        {
            "title": "Our class demo",
            "game_type": fruit_blender.pk,
            "file": _mp4(),
            "captions": _vtt(),
        },
    )
    assert response.url == reverse("library:home")
    video = Video.objects.get(owner=teacher)
    # Storage may add a suffix if the name exists (shared in-memory storage across tests).
    assert video.file.name.startswith(f"videos/{teacher.pk}/lesson") and video.captions_url


@pytest.mark.parametrize(
    ("upload", "error"),
    [
        ({"file": SimpleUploadedFile("a.avi", b"x", content_type="video/x-msvideo")}, ".mp4"),
        ({"file": _mp4(), "captions": _vtt(b"not a vtt")}, "WebVTT"),
        ({"file": _mp4(), "captions": _vtt(name="c.srt")}, ".vtt"),
    ],
)
def test_upload_validation(teacher_client, fruit_blender, upload, error):
    data = {"title": "x", "game_type": fruit_blender.pk, **upload}
    response = teacher_client.post(reverse("videos:upload"), data)
    assert response.status_code == 200 and error in response.content.decode()
    assert not Video.objects.filter(owner__isnull=False).exists()


@override_settings(MAX_VIDEO_UPLOAD_MB=1)
def test_upload_size_limit(teacher_client, fruit_blender):
    data = {"title": "big", "game_type": fruit_blender.pk, "file": _mp4(size=2 * 1024 * 1024)}
    response = teacher_client.post(reverse("videos:upload"), data)
    assert "too big" in response.content.decode()


def test_only_owner_can_delete_video(client, teacher, other_teacher, fruit_blender):
    video = Video.objects.create(owner=teacher, game_type=fruit_blender, title="Mine", file=_mp4())
    client.force_login(other_teacher)
    assert client.post(reverse("videos:delete", args=[video.pk])).status_code == 404
    client.force_login(teacher)
    client.post(reverse("videos:delete", args=[video.pk]))
    assert not Video.objects.filter(pk=video.pk).exists()


def test_default_video_cannot_be_deleted(teacher_client, fruit_blender):
    default = services.default_video(fruit_blender)
    assert teacher_client.post(reverse("videos:delete", args=[default.pk])).status_code == 404
