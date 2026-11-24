"""Step 6: live progress (MON-01) and student history (MON-02)."""

import pytest
from django.urls import reverse

from apps.accounts import services as account_services
from apps.classrooms import services as classroom_services
from apps.classrooms.models import Classroom, SessionParticipant
from apps.games import monitoring, services
from apps.games.models import GameType
from conftest import PASSWORD

pytestmark = pytest.mark.django_db


@pytest.fixture
def fruit_blender():
    return GameType.objects.get(key="fruit_blender")


@pytest.fixture
def session(classroom):
    return classroom_services.start_session(classroom)


def _join(student, session):
    classroom_services.join_session(student, session.code)
    return SessionParticipant.objects.get(session=session, student=student)


def _answer(round_, index, *answers, ms=2000):
    """Answer question `index` with the given answers; True = correct, int = that number."""
    q = round_.questions[index]
    for i, a in enumerate(answers):
        value = q["answer"] if a is True else a
        services.record_attempt(round_, q["id"], value, ms * (i + 1))


def _wrong(round_, index):
    return round_.questions[index]["answer"] + 1


# --- Live view ------------------------------------------------------------------------------
def test_live_rows_before_and_during_a_round(session, student, fruit_blender):
    participant = _join(student, session)
    [row] = monitoring.live_rows(session)
    assert row.current is None and row.rounds_done == 0

    r = services.start_round(participant, fruit_blender, "easy", "add")
    _answer(r, 0, True)  # right first time
    _answer(r, 1, _wrong(r, 1), True)  # one retry
    [row] = monitoring.live_rows(session)
    c = row.current
    assert (c.answered, c.total, c.first_try_right, c.retries) == (2, 5, 1, 1)
    assert c.percent_done == 40 and c.score_so_far == 50
    assert row.rounds_done == 0


def test_live_rows_count_finished_rounds_and_average(session, student, fruit_blender):
    participant = _join(student, session)
    for _ in range(2):
        r = services.start_round(participant, fruit_blender, "easy", "add")
        for i in range(5):
            _answer(r, i, True)
    r = services.start_round(participant, fruit_blender, "easy", "sub")
    _answer(r, 0, _wrong(r, 0), True)
    [row] = monitoring.live_rows(session)
    assert row.rounds_done == 2 and row.avg_score == 100
    assert row.current.round == r and row.current.score_so_far == 0


def test_live_rows_only_this_session(classroom, student, fruit_blender):
    old = classroom_services.start_session(classroom)
    services.start_round(_join(student, old), fruit_blender, "easy", "add")
    classroom_services.end_session(old)
    new = classroom_services.start_session(classroom)
    _join(student, new)
    [row] = monitoring.live_rows(new)
    assert row.current is None


def test_live_partial_shows_progress(teacher_client, session, student, fruit_blender):
    r = services.start_round(_join(student, session), fruit_blender, "easy", "add")
    _answer(r, 0, True)
    html = teacher_client.get(reverse("teach:session_live", args=[session.pk])).content.decode()
    assert "1/5" in html and "100%" in html
    assert reverse("teach:student_detail", args=[session.classroom_id, student.pk]) in html


def test_live_view_keeps_final_results_after_end(teacher_client, session, student, fruit_blender):
    r = services.start_round(_join(student, session), fruit_blender, "easy", "add")
    for i in range(5):
        _answer(r, i, True)
    classroom_services.end_session(session)
    response = teacher_client.get(reverse("teach:session_live", args=[session.pk]))
    assert response.status_code == 286
    html = response.content.decode()
    assert "Final results" in html and "Finished" in html


# --- History ------------------------------------------------------------------------------
def test_round_details_per_question(session, student, fruit_blender):
    r = services.start_round(_join(student, session), fruit_blender, "easy", "add")
    _answer(r, 0, _wrong(r, 0), _wrong(r, 0), True, ms=1000)
    [d] = monitoring.round_details([r])
    q0 = d.questions[0]
    assert [t.is_correct for t in q0.tries] == [False, False, True]
    assert q0.struggled and not q0.right_first_time and q0.solved
    assert q0.seconds == 3.0  # last try's time = time on the question (not the sum)
    assert d.questions[1].tries == []


def test_history_summary(session, student, fruit_blender):
    p = _join(student, session)
    r1 = services.start_round(p, fruit_blender, "easy", "add")
    for i in range(5):
        _answer(r1, i, True, ms=4000)
    r2 = services.start_round(p, fruit_blender, "medium", "sub")
    _answer(r2, 0, _wrong(r2, 0), _wrong(r2, 0), True)
    for i in range(1, 5):
        _answer(r2, i, True)
    r3 = services.start_round(p, fruit_blender, "easy", "add")  # unfinished
    _answer(r3, 0, True)

    rounds = monitoring.student_rounds(student, session.classroom.teacher)
    details = monitoring.round_details(rounds)
    s = monitoring.history_summary(rounds, details)
    assert (s.rounds_played, s.rounds_finished, s.avg_score) == (3, 2, 90)  # (100 + 80) / 2
    assert {(row["level"], row["kind"], row["avg"]) for row in s.by_level} == {
        ("Easy", "Adding", 100),
        ("Medium", "Taking away", 80),
    }
    assert s.struggled == [monitoring._question_text(r2.questions[0])]
    assert s.avg_seconds_per_question is not None


def test_history_hides_other_teachers_classes(teacher, other_teacher, student, fruit_blender):
    mine = Classroom.objects.create(teacher=teacher, name="Mine")
    theirs = Classroom.objects.create(teacher=other_teacher, name="Theirs")
    for c in (mine, theirs):
        s = classroom_services.start_session(c)
        services.start_round(_join(student, s), fruit_blender, "easy", "add")
    assert monitoring.student_rounds(student, teacher).count() == 1
    assert monitoring.student_rounds(student, other_teacher).count() == 1


def test_student_detail_page(teacher_client, session, student, fruit_blender):
    r = services.start_round(_join(student, session), fruit_blender, "easy", "add")
    _answer(r, 0, _wrong(r, 0), _wrong(r, 0), True)
    url = reverse("teach:student_detail", args=[session.classroom_id, student.pk])
    html = teacher_client.get(url).content.decode()
    assert student.full_name in html
    assert "Unfinished · 1/5" in html
    assert "answer--wrong" in html and "Needed extra help" in html


def test_student_detail_permissions(client, other_teacher, teacher, classroom, student):
    url = reverse("teach:student_detail", args=[classroom.pk, student.pk])
    client.force_login(other_teacher)
    assert client.get(url).status_code == 404  # not their class
    client.force_login(teacher)
    assert client.get(url).status_code == 404  # student not enrolled in this class
    outsider = account_services.create_student(full_name="Out", username="out", password=PASSWORD)
    client.force_login(outsider)
    assert client.get(url).status_code == 403  # students can't open teacher pages


def test_removed_student_history_still_viewable(teacher_client, session, student):
    _join(student, session)
    classroom_services.remove_student(session.classroom, student)
    url = reverse("teach:student_detail", args=[session.classroom_id, student.pk])
    assert "removed from this class" in teacher_client.get(url).content.decode()
