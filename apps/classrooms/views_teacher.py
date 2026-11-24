"""Teacher-side views: dashboard, classrooms, students, sessions (namespace "teach")."""

from django.contrib import messages
from django.db.models import Count, Q
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.accounts.decorators import teacher_required
from apps.accounts.forms import AccessibilityForm
from apps.accounts.models import StudentProfile, User
from apps.games import monitoring
from apps.games.models import GameType

from . import services
from .forms import AddStudentsForm, ClassroomForm
from .models import Classroom, ClassSession, Enrollment, SessionStatus
from .services import NewCredential

# HTMX stops an `every Ns` poll when the server answers with this status code.
HTMX_STOP_POLLING = 286
# Rounds shown in full on a student's history page (older ones still count in the summary).
HISTORY_ROUNDS = 30


def _my_classroom(request, pk) -> Classroom:
    # Every lookup is scoped to the logged-in teacher → other teachers get a 404.
    return get_object_or_404(Classroom, pk=pk, teacher=request.user)


def _my_session(request, pk) -> ClassSession:
    session = get_object_or_404(
        ClassSession.objects.select_related("classroom"), pk=pk, classroom__teacher=request.user
    )
    return services.refresh(session)


@teacher_required
def dashboard(request):
    services.expire_due_sessions()
    classrooms = (
        request.user.classrooms.filter(is_archived=False)
        .annotate(
            student_count=Count("enrollments", filter=Q(enrollments__is_active=True)),
            open_sessions=Count("sessions", filter=Q(sessions__status=SessionStatus.OPEN)),
        )
        .order_by("name")
    )
    return render(request, "classrooms/teacher/dashboard.html", {"classrooms": classrooms})


@teacher_required
def classroom_create(request):
    form = ClassroomForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        classroom = form.save(commit=False)
        classroom.teacher = request.user
        classroom.save()
        messages.success(request, _("Class created. Add your students next."))
        return redirect("teach:classroom_detail", pk=classroom.pk)
    return render(request, "classrooms/teacher/classroom_form.html", {"form": form})


@teacher_required
def classroom_edit(request, pk):
    classroom = _my_classroom(request, pk)
    form = ClassroomForm(request.POST or None, instance=classroom)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Class saved."))
        return redirect("teach:classroom_detail", pk=classroom.pk)
    return render(
        request, "classrooms/teacher/classroom_form.html", {"form": form, "classroom": classroom}
    )


@require_POST
@teacher_required
def classroom_archive(request, pk):
    classroom = _my_classroom(request, pk)
    if session := classroom.open_session:
        services.end_session(session)
    classroom.is_archived = True
    classroom.save(update_fields=["is_archived", "updated_at"])
    messages.success(request, _("Class removed."))
    return redirect("teach:dashboard")


@teacher_required
def classroom_detail(request, pk):
    classroom = _my_classroom(request, pk)
    services.expire_due_sessions()
    enrollments = classroom.enrollments.select_related("student").order_by("student__full_name")
    return render(
        request,
        "classrooms/teacher/classroom_detail.html",
        {
            "classroom": classroom,
            "active": [e for e in enrollments if e.is_active],
            "removed": [e for e in enrollments if not e.is_active],
            "open_session": classroom.open_session,
            "add_form": AddStudentsForm(),
            "games": GameType.objects.filter(is_playable=True),
        },
    )


@require_POST
@teacher_required
def students_add(request, pk):
    classroom = _my_classroom(request, pk)
    form = AddStudentsForm(request.POST)
    if not form.is_valid():
        for error in form.errors.get("names", []):
            messages.error(request, error)
        return redirect("teach:classroom_detail", pk=classroom.pk)
    credentials = services.add_students(classroom, form.cleaned_data["names"])
    return render(
        request,
        "classrooms/teacher/credentials.html",
        {"classroom": classroom, "credentials": credentials},
    )


def _student_in(classroom: Classroom, student_pk) -> User:
    enrollment = get_object_or_404(
        Enrollment.objects.select_related("student"), classroom=classroom, student_id=student_pk
    )
    return enrollment.student


@require_POST
@teacher_required
def student_remove(request, pk, student_pk):
    classroom = _my_classroom(request, pk)
    student = _student_in(classroom, student_pk)
    services.remove_student(classroom, student)
    messages.success(request, _("%(name)s was removed from the class.") % {"name": student})
    return redirect("teach:classroom_detail", pk=classroom.pk)


@require_POST
@teacher_required
def student_restore(request, pk, student_pk):
    classroom = _my_classroom(request, pk)
    student = _student_in(classroom, student_pk)
    services.restore_student(classroom, student)
    messages.success(request, _("%(name)s is back in the class.") % {"name": student})
    return redirect("teach:classroom_detail", pk=classroom.pk)


@require_POST
@teacher_required
def student_reset_password(request, pk, student_pk):
    classroom = _my_classroom(request, pk)
    student = _student_in(classroom, student_pk)
    password = services.reset_student_password(teacher=request.user, student=student)
    return render(
        request,
        "classrooms/teacher/credentials.html",
        {
            "classroom": classroom,
            "credentials": [NewCredential(student=student, password=password)],
            "is_reset": True,
        },
    )


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------
@require_POST
@teacher_required
def session_start(request, pk):
    classroom = _my_classroom(request, pk)
    if classroom.is_archived:
        return HttpResponseBadRequest("Archived class.")
    session = services.start_session(classroom)
    return redirect("teach:session_detail", pk=session.pk)


@teacher_required
def session_detail(request, pk):
    session = _my_session(request, pk)
    return render(
        request,
        "classrooms/teacher/session_detail.html",
        _live_context(session),
    )


@teacher_required
def session_live(request, pk):
    """HTMX partial polled every 5 s: status, time left, each student's progress (MON-01)."""
    session = _my_session(request, pk)
    return render(
        request,
        "classrooms/partials/teacher_live.html",
        _live_context(session),
        status=200 if session.is_open else HTMX_STOP_POLLING,
    )


def _live_context(session) -> dict:
    return {
        "session": session,
        "rows": monitoring.live_rows(session),
        "extend_choices": services.EXTEND_CHOICES_MINUTES,
    }


@teacher_required
def student_detail(request, pk, student_pk):
    """MON-02: one student's history in this teacher's classes, newest first."""
    classroom = _my_classroom(request, pk)
    enrollment = get_object_or_404(
        Enrollment.objects.select_related("student__student_profile"),
        classroom=classroom,
        student_id=student_pk,
    )
    student = enrollment.student
    profile, _created = StudentProfile.objects.get_or_create(user=student)
    # Bind on any POST: with every box unticked the POST can be empty (and `or None` would skip it).
    a11y_form = AccessibilityForm(
        request.POST if request.method == "POST" else None, instance=profile
    )
    if request.method == "POST" and a11y_form.is_valid():
        # A11Y-01: applies on the student's next page load (body classes + game config).
        a11y_form.save()
        messages.success(
            request, _("Accessibility settings saved for %(name)s.") % {"name": student}
        )
        return redirect("teach:student_detail", pk=classroom.pk, student_pk=student.pk)
    rounds = monitoring.student_rounds(student, request.user)
    details = monitoring.round_details(rounds[:HISTORY_ROUNDS])
    return render(
        request,
        "classrooms/teacher/student_detail.html",
        {
            "classroom": classroom,
            "student": student,
            "enrollment": enrollment,
            "a11y_form": a11y_form,
            "summary": monitoring.history_summary(rounds, details),
            "details": details,
            "shown": len(details),
            "struggle_tries": monitoring.STRUGGLE_TRIES,
        },
    )


@require_POST
@teacher_required
def session_extend(request, pk):
    session = _my_session(request, pk)
    try:
        minutes = int(request.POST.get("minutes", ""))
        services.extend_session(session, minutes)
    except ValueError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, _("Added %(m)s more minutes.") % {"m": minutes})
    return redirect("teach:session_detail", pk=session.pk)


@require_POST
@teacher_required
def session_end(request, pk):
    session = _my_session(request, pk)
    services.end_session(session)
    messages.success(request, _("Class time ended."))
    return redirect("teach:classroom_detail", pk=session.classroom_id)
