from django.contrib import admin

from .models import TutorialView, Video


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = ("title", "game_type", "owner", "static_path")
    list_filter = ("game_type",)


@admin.register(TutorialView)
class TutorialViewAdmin(admin.ModelAdmin):
    list_display = ("student", "game_type", "completed", "created_at")
