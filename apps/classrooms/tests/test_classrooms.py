from datetime import timedelta

import pytest
from django.contrib.auth import authenticate
from django.urls import reverse
from django.utils import timezone

from apps.accounts import services as account_services
from apps.classrooms import services
from apps.classrooms.models import (
    Classroom,
    ClassSession,
    Enrollment,
    SessionParticipant,
    SessionStatus,
)
from conftest import PASSWORD

pytestmark = pytest.mark.django_db


# --- Room codes & lifecycle -------------------------------------------------------
def test_code_uses_unambiguous_alphabet(classroom):
    session = services.start_session(classroom)
    assert len(session.code) == 6
    assert not set(session.code) & set("01OIL")


def test_start_session_returns_existing_open_one(classroom):
    assert services.start_session(classroom) == services.start_session(classroom)


def test_session_lasts_three_hours(classroom):
    session = services.start_session(classroom)
    assert (
        timedelta(hours=2, minutes=59)
        < session.expires_at - session.started_at
        <= timedelta(hours=3)
    )


def test_expired_session_ends_lazily_and_code_stops_working(classroom, student):
    session = services.start_session(classroom)
    ClassSession.objects.filter(pk=session.pk).update(expires_at=timezone.now())
    with pytest.raises(services.JoinError):
        services.join_session(student, session.code)
    session.refresh_from_db()
    assert session.status == SessionStatus.ENDED


def test_warning_window_and_extend(classroom):
    session = services.start_session(classroom)
    session.expires_at = timezone.now() + timedelta(minutes=4)
    session.save()
    assert session.in_warning_window
    services.extend_session(session, 30)
    assert not session.in_warning_window
    assert session.extended_count == 1
    with pytest.raises(ValueError):
        services.extend_session(session, 7)


def test_end_session(classroom):
    session = services.end_session(services.start_session(classroom))
    assert session.status == SessionStatus.ENDED
    with pytest.raises(ValueError):
        services.extend_session(session, 30)


def test_new_session_after_end_gets_fresh_row(classroom):
    first = services.end_session(services.start_session(classroom))
    assert services.start_session(classroom).pk != first.pk


# --- Joining ------------------------------------------------------------------------
def test_join_auto_enrolls_and_accepts_messy_code(classroom, student):
    session = services.start_session(classroom)
    messy = f" {session.code[:3].lower()}-{session.code[3:]} "
    assert services.join_session(student, messy) == session
    assert Enrollment.objects.filter(classroom=classroom, student=student, is_active=True).exists()
    assert SessionParticipant.objects.filter(session=session, student=student).exists()


def test_join_twice_is_idempotent(classroom, student):
    session = services.start_session(classroom)
    services.join_session(student, session.code)
    services.join_session(student, session.code)
    assert SessionParticipant.objects.filter(session=session).count() == 1


def test_bad_code(student):
    with pytest.raises(services.JoinError, match="doesn't work"):
        services.join_session(student, "ZZZZZZ")
    with pytest.raises(services.JoinError, match="6 letters"):
        services.join_session(student, "ABC")


def test_removed_student_cannot_rejoin(classroom, student):
    session = services.start_session(classroom)
    services.join_session(student, session.code)
    services.remove_student(classroom, student)
    with pytest.raises(services.JoinError, match="add you back"):
        services.join_session(student, session.code)
    services.restore_student(classroom, student)
    services.join_session(student, session.code)


def test_student_can_be_in_many_classrooms(teacher, other_teacher, student):
    a = Classroom.objects.create(teacher=teacher, name="A")
    b = Classroom.objects.create(teacher=other_teacher, name="B")
    services.join_session(student, services.start_session(a).code)
    services.join_session(student, services.start_session(b).code)
    assert student.enrollments.count() == 2


# --- Bulk add & passwords ---------------------------------------------------------------
def test_parse_names():
    assert services.parse_names(" Maria  Santos \n\nmaria santos, Juan Cruz") == [
        "Maria Santos",
        "Juan Cruz",
    ]


def test_add_students_creates_working_logins(classroom, teacher):
    creds = services.add_students(classroom, ["Maria Santos", "Juan Cruz"])
    assert [c.student.username for c in creds] == ["maria.s", "juan.c"]
    for c in creds:
        assert authenticate(username=c.student.username, password=c.password) == c.student
        assert c.student.created_by == teacher
    assert classroom.enrollments.count() == 2


def test_reset_password_only_for_my_students(classroom, teacher, other_teacher, student):
    with pytest.raises(PermissionError):
        services.reset_student_password(teacher=teacher, student=student)
    Enrollment.objects.create(classroom=classroom, student=student)
    new = services.reset_student_password(teacher=teacher, student=student)
    assert authenticate(username="maria", password=new) == student
    with pytest.raises(PermissionError):
        services.reset_student_password(teacher=other_teacher, student=student)


# --- Views & permissions -------------------------------------------------------------------
def test_teacher_flow_create_class_add_students_start_session(teacher_client, teacher):
    response = teacher_client.post(reverse("teach:classroom_create"), {"name": "Room 5"})
    classroom = Classroom.objects.get(name="Room 5", teacher=teacher)
    assert response.url == reverse("teach:classroom_detail", args=[classroom.pk])

    response = teacher_client.post(
        reverse("teach:students_add", args=[classroom.pk]), {"names": "Ana Lee\nBo Kim"}
    )
    assert response.status_code == 200
    assert "ana.l" in response.content.decode()

    response = teacher_client.post(reverse("teach:session_start", args=[classroom.pk]))
    session = classroom.sessions.get()
    assert response.url == reverse("teach:session_detail", args=[session.pk])
    page = teacher_client.get(response.url).content.decode()
    assert session.code in page


def test_other_teacher_gets_404(client, other_teacher, classroom):
    client.force_login(other_teacher)
    assert client.get(reverse("teach:classroom_detail", args=[classroom.pk])).status_code == 404
    session = services.start_session(classroom)
    assert client.get(reverse("teach:session_detail", args=[session.pk])).status_code == 404


def test_students_cannot_open_teacher_pages(student_client):
    assert student_client.get(reverse("teach:dashboard")).status_code == 403


def test_teachers_cannot_open_student_pages(teacher_client):
    assert teacher_client.get(reverse("play:join")).status_code == 403


def test_student_join_view_then_shortcut_back_to_session(student_client, classroom):
    session = services.start_session(classroom)
    response = student_client.post(reverse("play:join"), {"code": session.code})
    assert response.url == reverse("play:session", args=[session.pk])
    # Next visit to the code screen goes straight back into the open session.
    assert student_client.get(reverse("play:join")).url == response.url


def test_live_partial_stops_polling_when_ended(teacher_client, classroom):
    session = services.start_session(classroom)
    url = reverse("teach:session_live", args=[session.pk])
    assert teacher_client.get(url).status_code == 200
    services.end_session(session)
    assert teacher_client.get(url).status_code == 286


def test_student_status_shows_warning_then_ended(student_client, student, classroom):
    session = services.start_session(classroom)
    services.join_session(student, session.code)
    url = reverse("play:session_status", args=[session.pk])
    ClassSession.objects.filter(pk=session.pk).update(
        expires_at=timezone.now() + timedelta(minutes=3)
    )
    assert "5 minutes left" in student_client.get(url).content.decode()
    services.end_session(ClassSession.objects.get(pk=session.pk))
    response = student_client.get(url)
    assert response.status_code == 286
    assert "Great job" in response.content.decode()


def test_student_not_in_session_gets_404(client, classroom):
    outsider = account_services.create_student(full_name="Out", username="out", password=PASSWORD)
    client.force_login(outsider)
    session = services.start_session(classroom)
    assert client.get(reverse("play:session", args=[session.pk])).status_code == 404
