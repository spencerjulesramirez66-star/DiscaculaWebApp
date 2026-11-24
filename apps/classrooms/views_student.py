"""Student-side views: enter room code, session home, status polling (namespace "play")."""

from urllib.parse import urlencode

from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.accounts.decorators import student_required
from apps.games.models import Category, GameType

from . import services
from .forms import JoinForm
from .models import SessionParticipant
from .views_teacher import HTMX_STOP_POLLING

CATEGORY_HINTS = {
    Category.VISUAL: "See and move things",
    Category.KINESTHETIC: "Move and act",
    Category.AUDITORY: "Listen and answer",
}


def _game_menu() -> list[dict]:
    """Game cards grouped by category (GAM-01). Non-playable games show as 'Coming soon'."""
    games = list(GameType.objects.all())
    return [
        {
            "key": value,
            "name": label,
            "hint": CATEGORY_HINTS.get(value, ""),
            "games": [g for g in games if g.category == value],
        }
        for value, label in Category.choices
    ]


@student_required
def join(request):
    if request.method == "GET" and (session := services.active_session_for(request.user)):
        return redirect("play:session", pk=session.pk)
    form = JoinForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            session = services.join_session(request.user, form.cleaned_data["code"])
        except services.JoinError as exc:
            form.add_error("code", str(exc))
        else:
            session_url = reverse("play:session", args=[session.pk])
            profile = getattr(request.user, "student_profile", None)
            if profile is None or not profile.has_avatar:
                # First time ever: make a character before playing (docs/05-flows.md).
                return redirect(f"{reverse('accounts:avatar')}?{urlencode({'next': session_url})}")
            return redirect(session_url)
    return render(request, "classrooms/student/join.html", {"form": form})


def _my_participation(request, pk) -> SessionParticipant:
    participant = get_object_or_404(
        SessionParticipant.objects.select_related("session__classroom"),
        session_id=pk,
        student=request.user,
    )
    services.refresh(participant.session)
    return participant


@student_required
def session_home(request, pk):
    participant = _my_participation(request, pk)
    session = participant.session
    if not session.is_open:
        return render(request, "classrooms/student/session_ended.html", {"session": session})
    services.touch(participant)
    return render(
        request,
        "classrooms/student/session_home.html",
        {"session": session, "categories": _game_menu()},
    )


@student_required
def session_status(request, pk):
    """HTMX partial polled every 5 s: warning banner / ended notice; also marks presence."""
    participant = _my_participation(request, pk)
    is_open = participant.session.is_open
    if is_open:
        services.touch(participant)
    return render(
        request,
        "classrooms/partials/student_status.html",
        {"session": participant.session},
        status=200 if is_open else HTMX_STOP_POLLING,
    )
