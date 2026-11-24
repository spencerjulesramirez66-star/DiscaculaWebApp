"""Tutorial videos and who has watched them (GAM-09, CON-04/05). See docs/04-data-model.md."""

import os

from django.conf import settings
from django.db import models
from django.templatetags.static import static
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel


def _video_upload_to(instance, filename):
    return f"videos/{instance.owner_id or 'default'}/{os.path.basename(filename)}"


def _captions_upload_to(instance, filename):
    return f"captions/{instance.owner_id or 'default'}/{os.path.basename(filename)}"


class Video(TimeStampedModel):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="videos",
        help_text=_("Empty = a default video shipped with the app."),
    )
    game_type = models.ForeignKey("games.GameType", on_delete=models.CASCADE, related_name="videos")
    title = models.CharField(_("title"), max_length=120)
    # Teacher uploads use `file`; bundled placeholders use `static_path` (under static/).
    file = models.FileField(_("video file"), upload_to=_video_upload_to, blank=True)
    static_path = models.CharField(max_length=255, blank=True)
    captions = models.FileField(_("captions (.vtt)"), upload_to=_captions_upload_to, blank=True)
    static_captions_path = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["game_type", "title"]

    def __str__(self):
        return self.title

    @property
    def is_default(self) -> bool:
        return self.owner_id is None

    @property
    def url(self) -> str:
        if self.file:
            return self.file.url
        return static(self.static_path) if self.static_path else ""

    @property
    def captions_url(self) -> str:
        if self.captions:
            return self.captions.url
        return static(self.static_captions_path) if self.static_captions_path else ""

    @property
    def mime_type(self) -> str:
        name = (self.file.name if self.file else self.static_path).lower()
        return "video/webm" if name.endswith(".webm") else "video/mp4"


class TutorialView(TimeStampedModel):
    """A student watched (or finished) the tutorial for a game type."""

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tutorial_views"
    )
    game_type = models.ForeignKey(
        "games.GameType", on_delete=models.CASCADE, related_name="tutorial_views"
    )
    video = models.ForeignKey(Video, null=True, blank=True, on_delete=models.SET_NULL)
    completed = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["student", "game_type"], name="unique_tutorial_view"),
        ]

    def __str__(self):
        return f"{self.student} watched {self.game_type}"
