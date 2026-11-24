"""Teacher video library (CON-05). Tutorial playback for students lives in the games flow."""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.accounts.decorators import teacher_required

from .forms import VideoUploadForm
from .models import Video


@teacher_required
def video_upload(request):
    form = VideoUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        video = form.save(commit=False)
        video.owner = request.user
        video.save()
        messages.success(
            request, _("Video uploaded. To use it, open a class and choose it under Games.")
        )
        return redirect("library:home")
    return render(request, "content/video_upload.html", {"form": form})


@teacher_required
def video_view(request, pk):
    video = get_object_or_404(Video.objects.select_related("game_type"), pk=pk)
    if video.owner_id not in (None, request.user.pk):
        return redirect("library:home")
    return render(request, "content/video_view.html", {"video": video})


@require_POST
@teacher_required
def video_delete(request, pk):
    video = get_object_or_404(Video, pk=pk, owner=request.user)
    video.file.delete(save=False)
    if video.captions:
        video.captions.delete(save=False)
    video.delete()
    messages.success(request, _("Video deleted."))
    return redirect("library:home")
