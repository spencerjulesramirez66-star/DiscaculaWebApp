"""Shared round rules: start a round, record attempts, score, complete (works for every game)."""

import random
from dataclasses import dataclass

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.classrooms.models import SessionParticipant

from . import questions as question_utils
from .models import Attempt, Difficulty, GameRound, GameType, Operation, QuestionSet
from .registry import get_plugin

PLAYABLE_OPERATIONS = (Operation.ADD, Operation.SUB)


class RoundError(Exception):
    pass


def playable_game(key: str) -> GameType | None:
    game = GameType.objects.filter(key=key, is_playable=True).first()
    return game if game and get_plugin(game.key) else None


def resolve_question_set(
    game_type: GameType, difficulty: str, operation: str
) -> QuestionSet | None:
    """Which questions to use. Step 5 adds teacher/classroom choices; for now: the default set."""
    return (
        QuestionSet.objects.filter(
            game_type=game_type, owner__isnull=True, difficulty=difficulty, operation=operation
        )
        .order_by("pk")
        .first()
    )


def _a11y_flags(student) -> dict:
    profile = getattr(student, "student_profile", None)
    if profile is None:
        return {"reducedMotion": False, "narration": False, "keyboard": False}
    return {
        "reducedMotion": profile.reduced_motion,
        "narration": profile.narration,
        "keyboard": profile.keyboard_mode,
    }


@transaction.atomic
def start_round(
    participant: SessionParticipant, game_type: GameType, difficulty: str, operation: str
) -> GameRound:
    if difficulty not in Difficulty.values or operation not in PLAYABLE_OPERATIONS:
        raise RoundError("Pick a level and a kind of question.")
    plugin = get_plugin(game_type.key)
    if plugin is None:
        raise RoundError("This game isn't ready yet.")

    question_set = resolve_question_set(game_type, difficulty, operation)
    if question_set is not None:
        raw = question_utils.questions_for(question_set)
    else:  # no default set seeded for this combination → generate a fallback round
        raw = question_utils.generate(difficulty, operation, 5, random.Random())

    config = plugin.build_round_config(
        questions=raw, difficulty=difficulty, student=participant.student
    )
    config.update(
        {
            "game": game_type.key,
            "difficulty": difficulty,
            "operation": operation,
            "a11y": _a11y_flags(participant.student),
        }
    )
    round_ = GameRound.objects.create(
        student=participant.student,
        session=participant.session,
        game_type=game_type,
        question_set=question_set,
        difficulty=difficulty,
        operation=operation,
        config_snapshot=config,
    )
    participant.current_game = game_type
    participant.save(update_fields=["current_game", "updated_at"])
    return round_


def public_config(round_: GameRound, urls: dict) -> dict:
    """What the browser receives: the snapshot minus answers, plus endpoint URLs."""
    config = {**round_.config_snapshot, "roundId": round_.pk, "urls": urls}
    config["questions"] = [{k: v for k, v in q.items() if k != "answer"} for q in round_.questions]
    return config


@dataclass(frozen=True)
class AttemptResult:
    correct: bool
    try_number: int
    done: bool
    score_percent: int | None


def score_of(round_: GameRound) -> int:
    """GAM-06: % of questions answered right on the first try."""
    total = len(round_.questions)
    if not total:
        return 0
    first_try_right = round_.attempts.filter(try_number=1, is_correct=True).count()
    return round(100 * first_try_right / total)


def record_attempt(round_: GameRound, question_key: str, answer, time_ms: int) -> AttemptResult:
    """Server-checked answer (the browser is never trusted)."""
    question = next((q for q in round_.questions if q["id"] == question_key), None)
    if question is None:
        raise RoundError("Unknown question.")
    try:
        answer_int = int(answer)
    except (TypeError, ValueError) as exc:
        raise RoundError("Answer must be a number.") from exc

    with transaction.atomic():
        round_ = GameRound.objects.select_for_update().get(pk=round_.pk)
        if round_.is_complete:
            raise RoundError("This round is finished.")
        previous = round_.attempts.filter(question_key=question_key)
        if previous.filter(is_correct=True).exists():
            raise RoundError("Already answered.")
        plugin = get_plugin(round_.game_type.key)
        correct = plugin.check_answer(question, answer_int)
        try_number = previous.count() + 1
        try:
            Attempt.objects.create(
                round=round_,
                question_key=question_key,
                answer_given=answer_int,
                is_correct=correct,
                try_number=try_number,
                time_ms=max(0, min(int(time_ms or 0), 60 * 60 * 1000)),
            )
        except IntegrityError as exc:  # double-submit of the same try
            raise RoundError("Already recorded.") from exc

        answered = set(
            round_.attempts.filter(is_correct=True).values_list("question_key", flat=True)
        )
        done = answered >= {q["id"] for q in round_.questions}
        score = None
        if done:
            score = score_of(round_)
            round_.completed_at = timezone.now()
            round_.score_percent = score
            round_.save(update_fields=["completed_at", "score_percent", "updated_at"])
    return AttemptResult(correct=correct, try_number=try_number, done=done, score_percent=score)
