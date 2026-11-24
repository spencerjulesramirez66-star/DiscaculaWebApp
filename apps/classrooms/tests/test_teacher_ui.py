"""UI polish round: class page layout, student Manage section, dashboard count, question editor."""

import pytest
from django.urls import reverse

from apps.classrooms import services
from apps.classrooms.models import Enrollment
from apps.games import services as game_services
from apps.games.models import GameType, QuestionSet

pytestmark = pytest.mark.django_db


def test_dashboard_counts_each_student_once_with_class_time_history(teacher_client, classroom):
    services.add_students(classroom, ["Ana Lee", "Bo Kim"])
    for _ in range(3):  # several past class times used to multiply the count
        services.end_session(services.start_session(classroom))
    html = teacher_client.get(reverse("teach:dashboard")).content.decode()
    assert "2 students" in html and "6 students" not in html


def test_class_page_has_one_view_link_per_student_and_no_inline_actions(teacher_client, classroom):
    services.add_students(classroom, ["Ana Lee", "Bo Kim"])
    html = teacher_client.get(reverse("teach:classroom_detail", args=[classroom.pk])).content
    html = html.decode()
    assert html.count('class="person-list__link"') == 2
    assert "reset-password" not in html and "/remove/" not in html
    assert "Start class time" in html  # the one big action at the top


def test_class_page_shows_running_class_time_code(teacher_client, classroom):
    session = services.start_session(classroom)
    html = teacher_client.get(reverse("teach:classroom_detail", args=[classroom.pk])).content
    assert session.code in html.decode() and "Open class time" in html.decode()


def test_student_page_has_manage_actions(teacher_client, classroom, student):
    Enrollment.objects.create(classroom=classroom, student=student)
    url = reverse("teach:student_detail", args=[classroom.pk, student.pk])
    html = teacher_client.get(url).content.decode()
    assert "Give a new password" in html and "Remove from class" in html


def test_restore_returns_to_student_page(teacher_client, classroom, student):
    Enrollment.objects.create(classroom=classroom, student=student, is_active=False)
    response = teacher_client.post(
        reverse("teach:student_restore", args=[classroom.pk, student.pk])
    )
    assert response.url == reverse("teach:student_detail", args=[classroom.pk, student.pk])
    html = teacher_client.get(response.url).content.decode()
    assert "Remove from class" in html  # back in the class


def test_form_labels_have_no_trailing_colon(teacher_client):
    html = teacher_client.get(reverse("teach:classroom_create")).content.decode()
    assert "Class name</label>" in html and "Class name:</label>" not in html
    assert "Cancel" in html


def test_question_editor_has_add_button_and_blank_row_template(teacher_client, teacher):
    fb = GameType.objects.get(key="fruit_blender")
    default = QuestionSet.objects.get(
        game_type=fb, owner__isnull=True, difficulty="easy", operation="add"
    )
    mine = game_services.copy_question_set(default, teacher)
    html = teacher_client.get(reverse("library:set_edit", args=[mine.pk])).content.decode()
    assert "data-formset-add" in html and "__prefix__" in html
    # Count row markers only ("data-formset-rows" on the list itself also contains the text).
    assert html.count("data-formset-row>") == 5 + 1  # five saved rows + the template row
