import json
import random

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse

from apps.accounts import services as account_services
from apps.classrooms import services as classroom_services
from apps.classrooms.models import SessionParticipant
from apps.games import questions, services
from apps.games.models import (
    DIFFICULTY_MAX,
    GameRound,
    GameType,
    Question,
    QuestionSet,
)
from apps.games.registry import GamePlugin, get_plugin, register
from conftest import PASSWORD

pytestmark = pytest.mark.django_db


@pytest.fixture
def participant(classroom, student):
    session = classroom_services.start_session(classroom)
    classroom_services.join_session(student, session.code)
    return SessionParticipant.objects.get(session=session, student=student)


@pytest.fixture
def fruit_blender():
    return GameType.objects.get(key="fruit_blender")


@pytest.fixture
def round_(participant, fruit_blender):
    return services.start_round(participant, fruit_blender, "easy", "add")


def _post_attempt(client, round_, question_id, answer, time_ms=1500):
    return client.post(
        reverse("games:attempt", args=[round_.pk]),
        data=json.dumps({"questionId": question_id, "answer": answer, "timeMs": time_ms}),
        content_type="application/json",
    )


# --- Seed data & registry ------------------------------------------------------------
def test_seed_data_present_and_valid():
    assert GameType.objects.filter(is_playable=True).get().key == "fruit_blender"
    assert set(GameType.objects.values_list("category", flat=True)) == {
        "visual",
        "kinesthetic",
        "auditory",
    }
    assert QuestionSet.objects.filter(owner__isnull=True).count() == 6
    for q in Question.objects.select_related("question_set"):
        q.clean()  # raises if any default is out of range or negative


def test_registry_has_fruit_blender_and_rejects_duplicates():
    assert get_plugin("fruit_blender") is not None

    class Dupe(GamePlugin):
        key = "fruit_blender"

        def build_round_config(self, **kwargs):
            return {}

    with pytest.raises(ValueError):
        register(Dupe())


def test_question_validation_rejects_negative_and_out_of_range(fruit_blender):
    easy = QuestionSet.objects.get(game_type=fruit_blender, difficulty="easy", operation="sub")
    with pytest.raises(ValidationError):
        Question(question_set=easy, operand_a=2, operator="-", operand_b=3).clean()
    with pytest.raises(ValidationError):
        Question(question_set=easy, operand_a=4, operator="+", operand_b=3).clean()


# --- Question generation ----------------------------------------------------------------
@pytest.mark.parametrize("difficulty", ["easy", "medium", "hard"])
@pytest.mark.parametrize("operation", ["add", "sub", "mixed"])
def test_generated_questions_stay_in_range(difficulty, operation):
    rng = random.Random(1)
    limit = DIFFICULTY_MAX[difficulty]
    for q in questions.generate(difficulty, operation, 200, rng):
        assert 0 <= q["answer"] <= limit
        assert 1 <= q["a"] <= limit and 1 <= q["b"] <= limit


def test_answer_choices_unique_in_range_and_contain_answer():
    rng = random.Random(3)
    for answer in range(0, 6):
        choices = questions.answer_choices(answer, 5, rng)
        assert answer in choices
        assert len(set(choices)) == 3
        assert all(0 <= c <= 5 for c in choices)


# --- Rounds -------------------------------------------------------------------------------
def test_start_round_uses_default_set_and_marks_current_game(round_, participant):
    assert round_.question_set.is_default
    assert [q["a"] for q in round_.questions] == [1, 2, 2, 3, 1]
    participant.refresh_from_db()
    assert participant.current_game.key == "fruit_blender"


def test_public_config_hides_answers(round_):
    config = services.public_config(round_, {})
    assert all("answer" not in q for q in config["questions"])
    assert all(q["answer"] is not None for q in round_.questions)


def test_play_page_does_not_leak_answers(student_client, round_):
    html = student_client.get(reverse("games:round", args=[round_.pk])).content.decode()
    assert 'id="game-config"' in html
    assert '"answer"' not in html


def test_start_round_rejects_bad_choices(participant, fruit_blender):
    with pytest.raises(services.RoundError):
        services.start_round(participant, fruit_blender, "impossible", "add")
    with pytest.raises(services.RoundError):
        services.start_round(participant, fruit_blender, "easy", "mixed")


# --- Attempts & scoring ----------------------------------------------------------------------
def test_scoring_counts_first_tries_only(round_):
    qs = round_.questions
    # q1 wrong then right; others right first time → 4/5 = 80 %
    assert services.record_attempt(round_, qs[0]["id"], qs[0]["answer"] + 1, 900).correct is False
    second = services.record_attempt(round_, qs[0]["id"], qs[0]["answer"], 900)
    assert second.correct and second.try_number == 2
    for q in qs[1:-1]:
        assert services.record_attempt(round_, q["id"], q["answer"], 500).done is False
    last = services.record_attempt(round_, qs[-1]["id"], qs[-1]["answer"], 500)
    assert last.done and last.score_percent == 80
    round_.refresh_from_db()
    assert round_.is_complete and round_.score_percent == 80


def test_cannot_answer_twice_or_after_completion(round_):
    q = round_.questions[0]
    services.record_attempt(round_, q["id"], q["answer"], 100)
    with pytest.raises(services.RoundError, match="Already"):
        services.record_attempt(round_, q["id"], q["answer"], 100)
    for other in round_.questions[1:]:
        services.record_attempt(round_, other["id"], other["answer"], 100)
    with pytest.raises(services.RoundError, match="finished"):
        services.record_attempt(round_, q["id"], 0, 100)


def test_unknown_question_and_non_number(round_):
    with pytest.raises(services.RoundError):
        services.record_attempt(round_, "q99", 1, 0)
    with pytest.raises(services.RoundError):
        services.record_attempt(round_, "q1", "abc", 0)


# --- Views -----------------------------------------------------------------------------------
def test_full_round_through_http(student_client, participant):
    start_url = reverse("games:start", args=[participant.session_id, "fruit_blender"])
    tutorial_url = reverse("games:tutorial", args=[participant.session_id, "fruit_blender"])
    # First time: the how-to screen comes first (GAM-09).
    assert student_client.get(start_url).url == tutorial_url
    assert student_client.post(tutorial_url).url == start_url
    assert student_client.get(start_url).status_code == 200
    response = student_client.post(start_url, {"difficulty": "medium", "operation": "sub"})
    round_ = GameRound.objects.get()
    assert response.url == reverse("games:round", args=[round_.pk])

    for q in round_.questions:
        data = _post_attempt(student_client, round_, q["id"], q["answer"]).json()
        assert data["correct"] is True and data["sessionOpen"] is True
    assert data["done"] is True and data["score"] == 100

    result = student_client.get(reverse("games:result", args=[round_.pk]))
    assert "Congratulations" in result.content.decode() and "100%" in result.content.decode()
    # A finished round can't be replayed; its page forwards to the result.
    assert student_client.get(reverse("games:round", args=[round_.pk])).url.endswith("/result/")


def test_wrong_answer_via_http(student_client, round_):
    q = round_.questions[0]
    data = _post_attempt(student_client, round_, q["id"], q["answer"] + 1).json()
    assert data == {
        "correct": False,
        "tryNumber": 1,
        "done": False,
        "score": None,
        "sessionOpen": True,
    }


def test_session_end_lets_student_finish_current_question(student_client, round_):
    classroom_services.end_session(round_.session)
    q = round_.questions[0]
    data = _post_attempt(student_client, round_, q["id"], q["answer"]).json()
    assert data["correct"] is True and data["sessionOpen"] is False


def test_other_student_cannot_touch_my_round(client, round_):
    other = account_services.create_student(full_name="Other", username="oth", password=PASSWORD)
    client.force_login(other)
    assert client.get(reverse("games:round", args=[round_.pk])).status_code == 404
    assert _post_attempt(client, round_, "q1", 2).status_code == 404


def test_bad_json_and_conflicts_return_errors(student_client, round_):
    bad = student_client.post(
        reverse("games:attempt", args=[round_.pk]), data="{", content_type="application/json"
    )
    assert bad.status_code == 400
    assert _post_attempt(student_client, round_, "q99", 1).status_code == 409


def test_placeholder_games_are_not_playable(student_client, participant):
    url = reverse("games:start", args=[participant.session_id, "auditory_tba"])
    assert student_client.get(url).status_code == 404


def test_session_home_lists_games(student_client, participant):
    html = student_client.get(reverse("play:session", args=[participant.session_id])).content
    html = html.decode()
    assert "Fruit Blender" in html and "Coming soon" in html
    assert reverse("games:start", args=[participant.session_id, "fruit_blender"]) in html


def test_teacher_live_view_shows_current_game(teacher_client, round_):
    html = teacher_client.get(reverse("teach:session_live", args=[round_.session_id])).content
    assert "Fruit Blender" in html.decode()
