import os

from django import forms
from django.conf import settings
from django.utils.translation import gettext_lazy as _

from apps.games.models import GameType

from .models import Video

VIDEO_EXTENSIONS = {".mp4", ".webm"}
CAPTION_EXTENSIONS = {".vtt"}
MAX_CAPTIONS_BYTES = 512 * 1024


class VideoUploadForm(forms.ModelForm):
    """CON-05. Checks extension, size and (for captions) the WebVTT header."""

    class Meta:
        model = Video
        fields = ["title", "game_type", "file", "captions"]
        help_texts = {
            "file": _("An MP4 video, up to %(mb)s MB.") % {"mb": settings.MAX_VIDEO_UPLOAD_MB},
            "captions": _("Optional. A .vtt subtitles file, for students who can't hear well."),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["game_type"].queryset = GameType.objects.filter(is_playable=True)
        self.fields["game_type"].label = _("Game")
        self.fields["title"].label = _("Name")
        self.fields["file"].label = _("Video")
        self.fields["captions"].label = _("Subtitles file")
        self.fields["file"].required = True
        self.fields["file"].widget.attrs["accept"] = "video/mp4,video/webm"
        self.fields["captions"].widget.attrs["accept"] = ".vtt,text/vtt"

    def clean_file(self):
        f = self.cleaned_data.get("file")
        if not f:
            raise forms.ValidationError(_("Choose a video file."))
        if os.path.splitext(f.name)[1].lower() not in VIDEO_EXTENSIONS:
            raise forms.ValidationError(_("Please choose an MP4 video."))
        if f.size > settings.MAX_VIDEO_UPLOAD_MB * 1024 * 1024:
            raise forms.ValidationError(
                _("The video is too big. The limit is %(mb)s MB.")
                % {"mb": settings.MAX_VIDEO_UPLOAD_MB}
            )
        return f

    def clean_captions(self):
        f = self.cleaned_data.get("captions")
        if not f:
            return f
        if os.path.splitext(f.name)[1].lower() not in CAPTION_EXTENSIONS:
            raise forms.ValidationError(_("The subtitles file must end in .vtt."))
        if f.size > MAX_CAPTIONS_BYTES:
            raise forms.ValidationError(_("The subtitles file is too big."))
        head = f.read(16)
        f.seek(0)
        if not head.lstrip(b"\xef\xbb\xbf").startswith(b"WEBVTT"):
            raise forms.ValidationError(
                _("That subtitles file doesn't look right. It must be a .vtt file.")
            )
        return f
