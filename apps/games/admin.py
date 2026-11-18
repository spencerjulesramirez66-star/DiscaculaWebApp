from django.contrib import admin

from .models import Attempt, GameRound, GameType, Question, QuestionSet


@admin.register(GameType)
class GameTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "key", "category", "is_playable", "order")
    list_editable = ("is_playable", "order")


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 0


@admin.register(QuestionSet)
class QuestionSetAdmin(admin.ModelAdmin):
    list_display = ("title", "game_type", "difficulty", "operation", "mode", "owner")
    list_filter = ("game_type", "difficulty", "operation", "mode")
    inlines = [QuestionInline]


class AttemptInline(admin.TabularInline):
    model = Attempt
    extra = 0
    readonly_fields = ("question_key", "answer_given", "is_correct", "try_number", "time_ms")


@admin.register(GameRound)
class GameRoundAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "game_type",
        "difficulty",
        "operation",
        "score_percent",
        "started_at",
    )
    list_filter = ("game_type", "difficulty")
    inlines = [AttemptInline]
    readonly_fields = ("config_snapshot",)
