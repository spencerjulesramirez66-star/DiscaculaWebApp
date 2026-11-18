"""Teacher-side views: dashboard, classrooms, students, sessions (namespace "teach")."""

from django.contrib import messages
from django.db.models import Count, Q
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.accounts.decorators import teacher_required
from apps.accounts.models import User

from . import services
from .forms import AddStudentsForm, ClassroomForm
from .models import Classroom, ClassSession, Enrollment, SessionStatus
from .services import NewCredential

# HTMX stops an `every Ns` poll when the server answers with this status code.
HTMX_STOP_POLLING = 286


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
    messages.success(request, _("Class archived."))
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
        {"session": session, "extend_choices": services.EXTEND_CHOICES_MINUTES},
    )


@teacher_required
def session_live(request, pk):
    """HTMX partial polled every 5 s: status, time left, participants (MON-01 groundwork)."""
    session = _my_session(request, pk)
    participants = session.participants.select_related("student").order_by("student__full_name")
    return render(
        request,
        "classrooms/partials/teacher_live.html",
        {
            "session": session,
            "participants": participants,
            "extend_choices": services.EXTEND_CHOICES_MINUTES,
        },
        status=200 if session.is_open else HTMX_STOP_POLLING,
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
        messages.success(request, _("Session extended by %(m)s minutes.") % {"m": minutes})
    return redirect("teach:session_detail", pk=session.pk)


@require_POST
@teacher_required
def session_end(request, pk):
    session = _my_session(request, pk)
    services.end_session(session)
    messages.success(request, _("Session ended. The room code no longer works."))
    return redirect("teach:classroom_detail", pk=session.classroom_id)
