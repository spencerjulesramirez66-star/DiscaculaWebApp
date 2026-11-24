"""Games, questions, rounds and attempts. See docs/04-data-model.md and ADR-0005."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel


class Category(models.TextChoices):
    VISUAL = "visual", _("Visual")
    KINESTHETIC = "kinesthetic", _("Kinesthetic")
    AUDITORY = "auditory", _("Auditory")


class Difficulty(models.TextChoices):
    EASY = "easy", _("Easy")
    MEDIUM = "medium", _("Medium")
    HARD = "hard", _("Hard")


# GAM-03: biggest number allowed in a question *and* its answer, per difficulty.
DIFFICULTY_MAX = {Difficulty.EASY: 5, Difficulty.MEDIUM: 10, Difficulty.HARD: 20}


class Operation(models.TextChoices):
    ADD = "add", _("Adding")
    SUB = "sub", _("Taking away")
    MIXED = "mixed", _("Mixed")


class Operator(models.TextChoices):
    PLUS = "+", "+"
    MINUS = "-", "−"


class GameType(TimeStampedModel):
    key = models.SlugField(
        unique=True, help_text=_("Matches the plugin key and static/js/games/<key>/")
    )
    name = models.CharField(max_length=80)
    category = models.CharField(max_length=16, choices=Category.choices)
    description = models.CharField(max_length=160, blank=True)
    is_playable = models.BooleanField(default=False, help_text=_("False = 'Coming soon' card."))
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class QuestionMode(models.TextChoices):
    EXPLICIT = "explicit", _("Fixed list of questions")
    GENERATED = "generated", _("Generated from rules")


class QuestionSet(TimeStampedModel):
    game_type = models.ForeignKey(GameType, on_delete=models.CASCADE, related_name="question_sets")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="question_sets",
        help_text=_("Empty = a global default set (read-only)."),
    )
    copied_from = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="copies"
    )
    title = models.CharField(max_length=120)
    difficulty = models.CharField(max_length=8, choices=Difficulty.choices)
    operation = models.CharField(max_length=8, choices=Operation.choices)
    mode = models.CharField(max_length=10, choices=QuestionMode.choices, default="explicit")
    generator_params = models.JSONField(default=dict, blank=True)
    question_count = models.PositiveSmallIntegerField(default=5)

    class Meta:
        ordering = ["game_type", "difficulty", "operation", "title"]

    def __str__(self):
        return self.title

    @property
    def is_default(self) -> bool:
        return self.owner_id is None


class Question(TimeStampedModel):
    question_set = models.ForeignKey(
        QuestionSet, on_delete=models.CASCADE, related_name="questions"
    )
    operand_a = models.PositiveSmallIntegerField()
    operator = models.CharField(max_length=1, choices=Operator.choices)
    operand_b = models.PositiveSmallIntegerField()
    order = models.PositiveSmallIntegerField(default=0)
    extra = models.JSONField(default=dict, blank=True, help_text=_("Game-specific, e.g. fruit."))

    class Meta:
        ordering = ["order", "pk"]

    def __str__(self):
        return f"{self.operand_a} {self.operator} {self.operand_b}"

    @property
    def answer(self) -> int:
        if self.operator == Operator.PLUS:
            return self.operand_a + self.operand_b
        return self.operand_a - self.operand_b

    def clean(self):
        limit = DIFFICULTY_MAX[self.question_set.difficulty]
        if self.answer < 0:
            raise ValidationError(_("The answer can't be below zero."))
        if max(self.operand_a, self.operand_b, self.answer) > limit:
            raise ValidationError(
                _("Numbers must be %(max)s or less for this difficulty.") % {"max": limit}
            )


class GameRound(TimeStampedModel):
    """One play-through of a game. `config_snapshot` holds the exact questions served."""

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="game_rounds"
    )
    session = models.ForeignKey(
        "classrooms.ClassSession",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="game_rounds",
    )
    game_type = models.ForeignKey(GameType, on_delete=models.PROTECT, related_name="rounds")
    question_set = models.ForeignKey(
        QuestionSet, null=True, blank=True, on_delete=models.SET_NULL, related_name="rounds"
    )
    difficulty = models.CharField(max_length=8, choices=Difficulty.choices)
    operation = models.CharField(max_length=8, choices=Operation.choices)
    config_snapshot = models.JSONField(default=dict)
    started_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)
    score_percent = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.student} · {self.game_type} · {self.started_at:%Y-%m-%d %H:%M}"

    @property
    def is_complete(self) -> bool:
        return self.completed_at is not None

    @property
    def questions(self) -> list[dict]:
        return self.config_snapshot.get("questions", [])


class Attempt(TimeStampedModel):
    """One answer to one question (GAM-06/07). try_number 1 is the one that counts for score."""

    round = models.ForeignKey(GameRound, on_delete=models.CASCADE, related_name="attempts")
    question_key = models.CharField(max_length=16)
    answer_given = models.IntegerField()
    is_correct = models.BooleanField()
    try_number = models.PositiveSmallIntegerField()
    time_ms = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["round", "question_key", "try_number"], name="unique_attempt_try"
            ),
        ]

    def __str__(self):
        return f"{self.round_id}/{self.question_key} try {self.try_number}"


class ClassroomGameConfig(TimeStampedModel):
    """Per-classroom choices for one game (CON-03, CON-05).

    `question_sets`: the teacher's sets to use in this class. When a student picks a level and
    kind (e.g. Easy + Adding), the first assigned set that matches is used; otherwise the default.
    `video`: tutorial video for this class; empty = the default video.
    """

    classroom = models.ForeignKey(
        "classrooms.Classroom", on_delete=models.CASCADE, related_name="game_configs"
    )
    game_type = models.ForeignKey(GameType, on_delete=models.CASCADE, related_name="+")
    question_sets = models.ManyToManyField(
        QuestionSet, blank=True, related_name="classroom_configs"
    )
    video = models.ForeignKey(
        "content.Video", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["classroom", "game_type"], name="unique_classroom_game_config"
            ),
        ]

    def __str__(self):
        return f"{self.classroom} · {self.game_type}"
