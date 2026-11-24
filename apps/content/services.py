"""Which tutorial video to show, and whether a student still has to watch it (GAM-09)."""

from django.contrib.staticfiles import finders

from .models import TutorialView, Video


def default_video(game_type) -> Video | None:
    return Video.objects.filter(game_type=game_type, owner__isnull=True).order_by("pk").first()


def tutorial_video(game_type, classroom=None) -> Video | None:
    """The classroom's chosen video for this game, else the default one."""
    if classroom is not None:
        from apps.games.models import ClassroomGameConfig

        config = (
            ClassroomGameConfig.objects.filter(classroom=classroom, game_type=game_type)
            .select_related("video")
            .first()
        )
        if config and config.video:
            return config.video
    return default_video(game_type)


def video_is_playable(video: Video | None) -> bool:
    """False when there's no file yet (e.g. placeholder not added) → show written steps instead."""
    if video is None:
        return False
    if video.file:
        return True
    return bool(video.static_path and finders.find(video.static_path))


def needs_tutorial(student, game_type) -> bool:
    return not TutorialView.objects.filter(
        student=student, game_type=game_type, completed=True
    ).exists()


def mark_watched(student, game_type, video: Video | None) -> TutorialView:
    view, _created = TutorialView.objects.update_or_create(
        student=student,
        game_type=game_type,
        defaults={"video": video, "completed": True},
    )
    return view
