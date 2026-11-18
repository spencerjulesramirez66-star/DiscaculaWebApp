"""Student-side views: enter room code, session home, status polling (namespace "play")."""

from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.decorators import student_required

from . import services
from .forms import JoinForm
from .models import SessionParticipant
from .views_teacher import HTMX_STOP_POLLING

# Game categories shown on the session home. Real games arrive in build step 4.
CATEGORIES = [
    {"key": "visual", "name": "Visual", "hint": "See and move things"},
    {"key": "kinesthetic", "name": "Kinesthetic", "hint": "Move and act"},
    {"key": "auditory", "name": "Auditory", "hint": "Listen and answer"},
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
            return redirect("play:session", pk=session.pk)
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
        {"session": session, "categories": CATEGORIES},
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
