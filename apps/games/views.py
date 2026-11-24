"""Student game views: pick level → play round → post attempts → result (namespace "games")."""

import json

from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.accounts.decorators import student_required
from apps.classrooms import services as classroom_services
from apps.classrooms.models import SessionParticipant
from apps.content import services as content_services

from . import services
from .forms import StartRoundForm
from .models import GameRound


def _participant(request, session_pk) -> SessionParticipant:
    participant = get_object_or_404(
        SessionParticipant.objects.select_related("session__classroom"),
        session_id=session_pk,
        student=request.user,
    )
    classroom_services.refresh(participant.session)
    return participant


def _my_round(request, pk) -> GameRound:
    return get_object_or_404(
        GameRound.objects.select_related("game_type", "session"), pk=pk, student=request.user
    )


def _open_game(request, session_pk, key):
    participant = _participant(request, session_pk)
    game = services.playable_game(key)
    if game is None:
        raise Http404("Game not available.")
    return participant, game


@student_required
def game_tutorial(request, session_pk, key):
    """GAM-09: how-to video. First time: must reach the end (or press Done if it can't play)."""
    participant, game = _open_game(request, session_pk, key)
    if not participant.session.is_open:
        return redirect("play:session", pk=session_pk)
    video = content_services.tutorial_video(game, participant.session.classroom)
    if request.method == "POST":
        content_services.mark_watched(request.user, game, video)
        return redirect("games:start", session_pk=session_pk, key=key)
    first_time = content_services.needs_tutorial(request.user, game)
    return render(
        request,
        "games/tutorial.html",
        {
            "game": game,
            "session": participant.session,
            "video": video if content_services.video_is_playable(video) else None,
            "first_time": first_time,
            "a11y": getattr(request.user, "student_profile", None),
        },
    )


@student_required
def game_start(request, session_pk, key):
    participant, game = _open_game(request, session_pk, key)
    if not participant.session.is_open:
        return redirect("play:session", pk=session_pk)
    if content_services.needs_tutorial(request.user, game):
        return redirect("games:tutorial", session_pk=session_pk, key=key)
    form = StartRoundForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            round_ = services.start_round(
                participant, game, form.cleaned_data["difficulty"], form.cleaned_data["operation"]
            )
        except services.RoundError as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("games:round", pk=round_.pk)
    return render(
        request,
        "games/start.html",
        {"game": game, "session": participant.session, "form": form},
    )


@student_required
def round_play(request, pk):
    round_ = _my_round(request, pk)
    if round_.is_complete:
        return redirect("games:result", pk=round_.pk)
    config = services.public_config(
        round_,
        {
            "attempt": reverse("games:attempt", args=[round_.pk]),
            "result": reverse("games:result", args=[round_.pk]),
            "finish": reverse("play:join"),
        },
    )
    return render(request, "games/play.html", {"round": round_, "config": config})


@require_POST
@student_required
def round_attempt(request, pk):
    round_ = _my_round(request, pk)
    try:
        payload = json.loads(request.body or b"{}")
        result = services.record_attempt(
            round_,
            str(payload.get("questionId", "")),
            payload.get("answer"),
            payload.get("timeMs", 0),
        )
    except json.JSONDecodeError:
        return JsonResponse({"error": "Bad JSON."}, status=400)
    except services.RoundError as exc:
        return JsonResponse({"error": str(exc)}, status=409)
    session_open = round_.session is None or classroom_services.refresh(round_.session).is_open
    return JsonResponse(
        {
            "correct": result.correct,
            "tryNumber": result.try_number,
            "done": result.done,
            "score": result.score_percent,
            # SES-08: the client finishes the current question, then leaves if this is False.
            "sessionOpen": session_open,
        }
    )


@student_required
def round_result(request, pk):
    round_ = _my_round(request, pk)
    if not round_.is_complete:
        return redirect("games:round", pk=round_.pk)
    session_open = round_.session is not None and classroom_services.refresh(round_.session).is_open
    return render(
        request,
        "games/result.html",
        {"round": round_, "session_open": session_open},
    )
