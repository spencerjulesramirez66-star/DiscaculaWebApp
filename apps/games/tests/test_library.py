"""Step 5: teacher library (Copy & edit), classroom game settings, question-set resolution."""

import pytest
from django.urls import reverse

from apps.classrooms import services as classroom_services
from apps.classrooms.models import Classroom, SessionParticipant
from apps.games import services
from apps.games.models import ClassroomGameConfig, GameType, QuestionSet

pytestmark = pytest.mark.django_db


@pytest.fixture
def fruit_blender():
    return GameType.objects.get(key="fruit_blender")


@pytest.fixture
def easy_add(fruit_blender):
    return QuestionSet.objects.get(
        game_type=fruit_blender, owner__isnull=True, difficulty="easy", operation="add"
    )


def _formset_data(qset, rows, title="My set"):
    """POST data for set_edit: existing questions first, then new rows."""
    existing = list(qset.questions.order_by("order", "pk"))
    data = {
        "title": title,
        "q-TOTAL_FORMS": str(len(rows)),
        "q-INITIAL_FORMS": str(len(existing)),
        "q-MIN_NUM_FORMS": "0",
        "q-MAX_NUM_FORMS": "20",
    }
    for i, row in enumerate(rows):
        a, b, delete = (*row, False) if len(row) == 2 else row
        data[f"q-{i}-operand_a"] = "" if a is None else str(a)
        data[f"q-{i}-operand_b"] = "" if b is None else str(b)
        if i < len(existing):
            data[f"q-{i}-id"] = str(existing[i].pk)
            if delete:
                data[f"q-{i}-DELETE"] = "on"
    return data


def test_copy_makes_an_owned_editable_copy(teacher, easy_add):
    copy = services.copy_question_set(easy_add, teacher)
    assert copy.owner == teacher and copy.copied_from == easy_add
    assert copy.questions.count() == easy_add.questions.count()
    assert copy.title == "Easy adding – my version"


def test_copy_and_edit_through_views(teacher_client, teacher, easy_add):
    response = teacher_client.post(reverse("library:set_copy", args=[easy_add.pk]))
    copy = QuestionSet.objects.get(owner=teacher)
    assert response.url == reverse("library:set_edit", args=[copy.pk])
    assert teacher_client.get(response.url).status_code == 200

    # Change q1, delete q2, keep the rest, add one new question.
    rows = [(3, 1), (2, 1, True), (2, 2), (3, 2), (1, 4), (0, 5)]
    response = teacher_client.post(response.url, _formset_data(copy, rows, "Friday practice"))
    assert response.url == reverse("library:home")
    copy.refresh_from_db()
    assert copy.title == "Friday practice"
    assert [(q.operand_a, q.operand_b) for q in copy.questions.all()] == [
        (3, 1),
        (2, 2),
        (3, 2),
        (1, 4),
        (0, 5),
    ]
    assert copy.question_count == 5
    assert all(q.operator == "+" for q in copy.questions.all())


def test_edit_rejects_out_of_range_numbers(teacher_client, teacher, easy_add):
    copy = services.copy_question_set(easy_add, teacher)
    rows = [(9, 9)] + [(q.operand_a, q.operand_b) for q in copy.questions.all()[1:]]
    response = teacher_client.post(
        reverse("library:set_edit", args=[copy.pk]), _formset_data(copy, rows)
    )
    assert response.status_code == 200
    assert "5 or less" in response.content.decode()


def test_edit_rejects_negative_subtraction(teacher_client, teacher, fruit_blender):
    easy_sub = QuestionSet.objects.get(
        game_type=fruit_blender, owner__isnull=True, difficulty="easy", operation="sub"
    )
    copy = services.copy_question_set(easy_sub, teacher)
    rows = [(1, 3)] + [(q.operand_a, q.operand_b) for q in copy.questions.all()[1:]]
    response = teacher_client.post(
        reverse("library:set_edit", args=[copy.pk]), _formset_data(copy, rows)
    )
    assert "below zero" in response.content.decode()


def test_cannot_delete_every_question(teacher_client, teacher, easy_add):
    copy = services.copy_question_set(easy_add, teacher)
    rows = [(q.operand_a, q.operand_b, True) for q in copy.questions.all()]
    response = teacher_client.post(
        reverse("library:set_edit", args=[copy.pk]), _formset_data(copy, rows)
    )
    assert "at least one question" in response.content.decode()
    assert copy.questions.count() == 5


def test_defaults_and_other_teachers_sets_are_not_editable(
    client, teacher, other_teacher, easy_add
):
    client.force_login(teacher)
    assert client.get(reverse("library:set_edit", args=[easy_add.pk])).status_code == 404
    theirs = services.copy_question_set(easy_add, other_teacher)
    assert client.get(reverse("library:set_edit", args=[theirs.pk])).status_code == 404
    assert client.post(reverse("library:set_delete", args=[theirs.pk])).status_code == 404
    assert client.post(reverse("library:set_copy", args=[theirs.pk])).status_code == 404


def test_library_home_lists_defaults_and_mine(teacher_client, teacher, easy_add):
    services.copy_question_set(easy_add, teacher)
    html = teacher_client.get(reverse("library:home")).content.decode()
    assert "Easy adding" in html and "my version" in html
    assert "How to play Fruit Blender" in html  # seeded default video


# --- Classroom game settings & which set a round uses --------------------------------------
def test_assigned_set_is_used_for_matching_level_only(classroom, teacher, student, easy_add):
    mine = services.copy_question_set(easy_add, teacher)
    mine.questions.update(operand_a=4, operand_b=1)
    config = ClassroomGameConfig.objects.create(classroom=classroom, game_type=easy_add.game_type)
    config.question_sets.add(mine)

    assert services.resolve_question_set(easy_add.game_type, "easy", "add", classroom) == mine
    assert services.resolve_question_set(easy_add.game_type, "easy", "sub", classroom).is_default
    other_class = Classroom.objects.create(teacher=teacher, name="Other")
    assert services.resolve_question_set(easy_add.game_type, "easy", "add", other_class).is_default

    session = classroom_services.start_session(classroom)
    classroom_services.join_session(student, session.code)
    participant = SessionParticipant.objects.get(session=session)
    round_ = services.start_round(participant, easy_add.game_type, "easy", "add")
    assert round_.question_set == mine
    assert {(q["a"], q["b"]) for q in round_.questions} == {(4, 1)}


def test_class_game_settings_view(teacher_client, teacher, classroom, easy_add):
    mine = services.copy_question_set(easy_add, teacher)
    url = reverse("library:class_game", args=[classroom.pk, "fruit_blender"])
    assert teacher_client.get(url).status_code == 200
    response = teacher_client.post(url, {"question_sets": [mine.pk], "video": ""})
    assert response.url == reverse("teach:classroom_detail", args=[classroom.pk])
    config = ClassroomGameConfig.objects.get(classroom=classroom)
    assert list(config.question_sets.all()) == [mine]
    assert config.video is None


def test_class_game_settings_refuses_other_teachers_sets(
    teacher_client, other_teacher, classroom, easy_add
):
    theirs = services.copy_question_set(easy_add, other_teacher)
    url = reverse("library:class_game", args=[classroom.pk, "fruit_blender"])
    response = teacher_client.post(url, {"question_sets": [theirs.pk]})
    assert response.status_code == 200  # form error, nothing saved
    assert not ClassroomGameConfig.objects.get(classroom=classroom).question_sets.exists()


def test_class_game_settings_other_teacher_404(client, other_teacher, classroom):
    client.force_login(other_teacher)
    url = reverse("library:class_game", args=[classroom.pk, "fruit_blender"])
    assert client.get(url).status_code == 404
