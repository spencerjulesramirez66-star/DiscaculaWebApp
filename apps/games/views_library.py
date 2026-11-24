"""Teacher library: question sets (Copy & edit) and per-class game settings ("library")."""

from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.accounts.decorators import teacher_required
from apps.classrooms.models import Classroom
from apps.content.models import Video

from . import services
from .forms import ClassroomGameConfigForm, QuestionFormSet, QuestionSetForm
from .models import ClassroomGameConfig, GameType, QuestionSet


@teacher_required
def library_home(request):
    sets = list(services.visible_sets(request.user))
    videos = Video.objects.filter(owner__isnull=True) | Video.objects.filter(owner=request.user)
    return render(
        request,
        "games/library/home.html",
        {
            "default_sets": [s for s in sets if s.is_default],
            "my_sets": [s for s in sets if not s.is_default],
            "videos": videos.select_related("game_type").order_by("owner_id", "title"),
        },
    )


@require_POST
@teacher_required
def set_copy(request, pk):
    source = get_object_or_404(services.visible_sets(request.user), pk=pk)
    copy = services.copy_question_set(source, request.user)
    messages.success(request, _("Copied. Change the questions below, then save."))
    return redirect("library:set_edit", pk=copy.pk)


@teacher_required
def set_edit(request, pk):
    qset = get_object_or_404(QuestionSet, pk=pk, owner=request.user)  # defaults are read-only
    form = QuestionSetForm(request.POST or None, instance=qset)
    formset = QuestionFormSet(request.POST or None, instance=qset, prefix="q")
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        with transaction.atomic():
            form.save()
            formset.save(commit=False)
            for obj in formset.deleted_objects:
                obj.delete()
            # Order = row position on the form, so new rows land where the teacher typed them.
            order = 0
            for qform in formset.forms:
                if not qform.cleaned_data or qform.cleaned_data.get("DELETE"):
                    continue  # untouched blank row, or deleted
                qform.instance.order = order
                qform.instance.save()
                order += 1
            qset.question_count = qset.questions.count()
            qset.save(update_fields=["question_count", "updated_at"])
        messages.success(request, _("Question set saved."))
        return redirect("library:home")
    return render(
        request, "games/library/set_edit.html", {"qset": qset, "form": form, "formset": formset}
    )


@teacher_required
def set_view(request, pk):
    """Read-only view of any set the teacher can see (used for defaults)."""
    qset = get_object_or_404(services.visible_sets(request.user), pk=pk)
    return render(request, "games/library/set_view.html", {"qset": qset})


@require_POST
@teacher_required
def set_delete(request, pk):
    qset = get_object_or_404(QuestionSet, pk=pk, owner=request.user)
    qset.delete()
    messages.success(request, _("Question set deleted."))
    return redirect("library:home")


@teacher_required
def classroom_game_settings(request, pk, key):
    classroom = get_object_or_404(Classroom, pk=pk, teacher=request.user)
    game = get_object_or_404(GameType, key=key, is_playable=True)
    config, _created = ClassroomGameConfig.objects.get_or_create(
        classroom=classroom, game_type=game
    )
    form = ClassroomGameConfigForm(
        request.POST or None, instance=config, teacher=request.user, game_type=game
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Game settings saved for %(c)s.") % {"c": classroom.name})
        return redirect("teach:classroom_detail", pk=classroom.pk)
    return render(
        request,
        "games/library/classroom_game_settings.html",
        {"classroom": classroom, "game": game, "form": form},
    )
