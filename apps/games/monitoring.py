"""Teacher monitoring (MON-01 live view, MON-02 history). Read-only summaries of rounds/attempts.

Works for every game because it only reads the generic GameRound/Attempt tables (ADR-0005).
Definitions (also in docs/GLOSSARY.md):
- answered      = questions with a correct attempt
- first-try %   = questions right on try 1 ÷ questions answered (live) or ÷ all questions (final)
- retries       = wrong attempts
"""

from collections import defaultdict
from dataclasses import dataclass, field

from django.db.models import Avg, Count, Q

from .models import Attempt, GameRound

# A question needing this many tries or more is flagged for the teacher.
STRUGGLE_TRIES = 3


@dataclass
class RoundProgress:
    round: GameRound
    total: int
    answered: int
    first_try_right: int
    retries: int

    @property
    def percent_done(self) -> int:
        return round(100 * self.answered / self.total) if self.total else 0

    @property
    def score_so_far(self) -> int | None:
        """First-try % over the questions answered so far (None before the first answer)."""
        return round(100 * self.first_try_right / self.answered) if self.answered else None


def _progress_for(rounds) -> dict[int, RoundProgress]:
    rounds = list(rounds)
    stats = (
        Attempt.objects.filter(round__in=rounds)
        .values("round_id")
        .annotate(
            answered=Count("question_key", filter=Q(is_correct=True), distinct=True),
            first_try_right=Count("pk", filter=Q(try_number=1, is_correct=True)),
            retries=Count("pk", filter=Q(is_correct=False)),
        )
    )
    by_round = {row["round_id"]: row for row in stats}
    out = {}
    for r in rounds:
        row = by_round.get(r.pk, {})
        out[r.pk] = RoundProgress(
            round=r,
            total=len(r.questions),
            answered=row.get("answered", 0),
            first_try_right=row.get("first_try_right", 0),
            retries=row.get("retries", 0),
        )
    return out


@dataclass
class LiveRow:
    participant: object
    current: RoundProgress | None
    rounds_done: int
    avg_score: int | None


def live_rows(session) -> list[LiveRow]:
    """One row per student in the session: their latest round's progress + finished rounds."""
    participants = list(
        session.participants.select_related("student__student_profile", "current_game").order_by(
            "student__full_name"
        )
    )
    rounds = (
        GameRound.objects.filter(session=session)
        .select_related("game_type")
        .order_by("student_id", "-started_at")
    )
    latest, done_scores = {}, defaultdict(list)
    for r in rounds:
        latest.setdefault(r.student_id, r)
        if r.is_complete:
            done_scores[r.student_id].append(r.score_percent)
    progress = _progress_for(latest.values())
    rows = []
    for p in participants:
        current = latest.get(p.student_id)
        scores = done_scores.get(p.student_id, [])
        rows.append(
            LiveRow(
                participant=p,
                current=progress[current.pk] if current else None,
                rounds_done=len(scores),
                avg_score=round(sum(scores) / len(scores)) if scores else None,
            )
        )
    return rows


# ---------------------------------------------------------------------------
# History (MON-02)
# ---------------------------------------------------------------------------
@dataclass
class QuestionDetail:
    key: str
    text: str
    answer: int
    tries: list = field(default_factory=list)  # Attempt rows, in order

    @property
    def right_first_time(self) -> bool:
        return bool(self.tries) and self.tries[0].is_correct

    @property
    def solved(self) -> bool:
        return any(t.is_correct for t in self.tries)

    @property
    def seconds(self) -> float | None:
        # Each try's time is measured from when the question appeared, so the last try's
        # time is the total time spent on the question (don't sum them).
        return round(max(t.time_ms for t in self.tries) / 1000, 1) if self.tries else None

    @property
    def struggled(self) -> bool:
        return len(self.tries) >= STRUGGLE_TRIES


@dataclass
class RoundDetail:
    progress: RoundProgress
    questions: list[QuestionDetail]

    @property
    def round(self) -> GameRound:
        return self.progress.round


def _question_text(q: dict) -> str:
    sign = "+" if q.get("op") == "+" else "−"
    return f"{q['a']} {sign} {q['b']}"


def round_details(rounds) -> list[RoundDetail]:
    rounds = list(rounds)
    progress = _progress_for(rounds)
    attempts = defaultdict(list)
    for a in Attempt.objects.filter(round__in=rounds).order_by(
        "round_id", "question_key", "try_number"
    ):
        attempts[(a.round_id, a.question_key)].append(a)
    details = []
    for r in rounds:
        questions = [
            QuestionDetail(
                key=q["id"],
                text=_question_text(q),
                answer=q["answer"],
                tries=attempts.get((r.pk, q["id"]), []),
            )
            for q in r.questions
        ]
        details.append(RoundDetail(progress=progress[r.pk], questions=questions))
    return details


@dataclass
class HistorySummary:
    rounds_played: int
    rounds_finished: int
    avg_score: int | None
    avg_seconds_per_question: float | None
    by_level: list[dict]
    struggled: list[str]  # question texts that needed STRUGGLE_TRIES+ tries, most recent first


def student_rounds(student, teacher):
    """A student's rounds in this teacher's classes (teachers never see other teachers' data)."""
    return (
        GameRound.objects.filter(student=student, session__classroom__teacher=teacher)
        .select_related("game_type", "session__classroom")
        .order_by("-started_at")
    )


def history_summary(rounds_qs, details: list[RoundDetail]) -> HistorySummary:
    finished = rounds_qs.filter(completed_at__isnull=False)
    avg = finished.aggregate(v=Avg("score_percent"))["v"]
    times = Attempt.objects.filter(round__in=rounds_qs, is_correct=True).aggregate(
        v=Avg("time_ms")
    )["v"]
    by_level = list(
        finished.values("game_type__name", "difficulty", "operation")
        .annotate(rounds=Count("pk"), avg=Avg("score_percent"))
        .order_by("game_type__name", "difficulty", "operation")
    )
    labels = {
        "easy": "Easy",
        "medium": "Medium",
        "hard": "Hard",
        "add": "Adding",
        "sub": "Taking away",
    }
    for row in by_level:
        row["level"] = labels.get(row["difficulty"], row["difficulty"])
        row["kind"] = labels.get(row["operation"], row["operation"])
        row["avg"] = round(row["avg"])
    struggled = []
    for d in details:
        for q in d.questions:
            if q.struggled and q.text not in struggled:
                struggled.append(q.text)
    return HistorySummary(
        rounds_played=rounds_qs.count(),
        rounds_finished=finished.count(),
        avg_score=round(avg) if avg is not None else None,
        avg_seconds_per_question=round(times / 1000, 1) if times is not None else None,
        by_level=by_level,
        struggled=struggled[:8],
    )
