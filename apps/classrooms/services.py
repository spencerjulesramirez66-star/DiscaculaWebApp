"""Classroom & session rules (SES-*). Views stay thin; everything testable lives here."""

import secrets
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts import services as account_services
from apps.accounts.models import User

from .models import Classroom, ClassSession, Enrollment, SessionParticipant, SessionStatus

# No 0/O, 1/I/L — easy to read off a board and type (SES-03).
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 6
EXTEND_CHOICES_MINUTES = (30, 60)


class JoinError(Exception):
    """Raised with a kid-friendly message."""


@dataclass(frozen=True)
class NewCredential:
    student: User
    password: str


# ---------------------------------------------------------------------------
# Who may see what
# ---------------------------------------------------------------------------
def teacher_students(teacher: User):
    """Students a teacher may manage: enrolled in one of their classes, or created by them."""
    return User.objects.filter(
        Q(enrollments__classroom__teacher=teacher) | Q(created_by=teacher),
        role="student",
    ).distinct()


def teacher_can_manage_student(teacher: User, student: User) -> bool:
    return teacher.is_teacher and teacher_students(teacher).filter(pk=student.pk).exists()


def reset_student_password(*, teacher: User, student: User) -> str:
    """ACC-09: returns the new readable password to show once."""
    if not teacher_can_manage_student(teacher, student):
        raise PermissionError("Teacher cannot manage this student.")
    return account_services.set_new_kid_password(student)


# ---------------------------------------------------------------------------
# Students in a classroom
# ---------------------------------------------------------------------------
def parse_names(raw: str) -> list[str]:
    """One name per line (or comma-separated); blanks and duplicates removed, order kept."""
    seen, names = set(), []
    for chunk in raw.replace(",", "\n").splitlines():
        name = " ".join(chunk.split())
        if name and name.lower() not in seen:
            seen.add(name.lower())
            names.append(name)
    return names


@transaction.atomic
def add_students(classroom: Classroom, names: list[str]) -> list[NewCredential]:
    """ACC-05: create accounts with readable credentials and enroll them."""
    created = []
    for name in names:
        password = account_services.generate_kid_password()
        student = account_services.create_student(
            full_name=name, password=password, created_by=classroom.teacher
        )
        Enrollment.objects.create(classroom=classroom, student=student)
        created.append(NewCredential(student=student, password=password))
    return created


def remove_student(classroom: Classroom, student: User) -> None:
    Enrollment.objects.filter(classroom=classroom, student=student).update(is_active=False)


def restore_student(classroom: Classroom, student: User) -> None:
    Enrollment.objects.filter(classroom=classroom, student=student).update(is_active=True)


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------
def normalize_code(raw: str) -> str:
    return "".join(ch for ch in raw.upper() if ch.isalnum())


def expire_due_sessions() -> int:
    """End every open session past its time. Called lazily — no background worker needed."""
    now = timezone.now()
    due = ClassSession.objects.filter(status=SessionStatus.OPEN, expires_at__lte=now)
    return due.update(status=SessionStatus.ENDED, ended_at=now)


def refresh(session: ClassSession) -> ClassSession:
    """Re-read a session, ending it first if its time is up."""
    if session.status == SessionStatus.OPEN and timezone.now() >= session.expires_at:
        session.status = SessionStatus.ENDED
        session.ended_at = session.expires_at
        session.save(update_fields=["status", "ended_at", "updated_at"])
    return session


def _new_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def start_session(classroom: Classroom) -> ClassSession:
    """SES-03: start a session, or return the one already open for this classroom."""
    expire_due_sessions()
    if existing := classroom.open_session:
        return existing
    now = timezone.now()
    for _attempt in range(10):
        try:
            with transaction.atomic():
                return ClassSession.objects.create(
                    classroom=classroom,
                    code=_new_code(),
                    started_at=now,
                    expires_at=now + timedelta(hours=settings.SESSION_EXPIRY_HOURS),
                )
        except IntegrityError:
            # Code collision (or a parallel start) — the DB constraint caught it; try again.
            if existing := classroom.open_session:
                return existing
    raise RuntimeError("Could not allocate a unique room code.")


def extend_session(session: ClassSession, minutes: int) -> ClassSession:
    """SES-06: add time to an open session."""
    if minutes not in EXTEND_CHOICES_MINUTES:
        raise ValueError(f"Extend by one of {EXTEND_CHOICES_MINUTES} minutes.")
    refresh(session)
    if not session.is_open:
        raise ValueError("Session already ended.")
    session.expires_at += timedelta(minutes=minutes)
    session.extended_count += 1
    session.save(update_fields=["expires_at", "extended_count", "updated_at"])
    return session


def end_session(session: ClassSession) -> ClassSession:
    """SES-09: teacher ends the session now."""
    if session.status == SessionStatus.OPEN:
        session.status = SessionStatus.ENDED
        session.ended_at = timezone.now()
        session.save(update_fields=["status", "ended_at", "updated_at"])
    return session


def join_session(student: User, raw_code: str) -> ClassSession:
    """SES-04: enter a room code → auto-enroll if new → join."""
    code = normalize_code(raw_code)
    if len(code) != CODE_LENGTH:
        raise JoinError("Room codes have 6 letters and numbers. Check it with your teacher.")
    # Outside the transaction below: a failed join must not roll back the expiry.
    expire_due_sessions()
    with transaction.atomic():
        return _join_open_session(student, code)


def _join_open_session(student: User, code: str) -> ClassSession:
    session = (
        ClassSession.objects.select_related("classroom")
        .filter(code=code, status=SessionStatus.OPEN)
        .first()
    )
    if session is None or session.classroom.is_archived:
        raise JoinError("That code doesn't work. Check it with your teacher.")

    enrollment, _created = Enrollment.objects.get_or_create(
        classroom=session.classroom, student=student
    )
    if not enrollment.is_active:
        raise JoinError("Ask your teacher to add you back to this class.")

    participant, created = SessionParticipant.objects.get_or_create(
        session=session, student=student
    )
    if not created:
        touch(participant)
    return session


def touch(participant: SessionParticipant) -> None:
    """Mark a student as still here (called by the student's 5 s poll)."""
    participant.last_seen_at = timezone.now()
    participant.save(update_fields=["last_seen_at", "updated_at"])


def active_session_for(student: User) -> ClassSession | None:
    """The open session a student is already in, if any — lets them skip the code screen."""
    expire_due_sessions()
    return (
        ClassSession.objects.filter(
            status=SessionStatus.OPEN,
            participants__student=student,
            classroom__enrollments__student=student,
            classroom__enrollments__is_active=True,
        )
        .order_by("-started_at")
        .first()
    )
