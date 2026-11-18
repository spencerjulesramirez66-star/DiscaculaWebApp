"""Classrooms, enrollment and live sessions. See docs/04-data-model.md and docs/05-flows.md."""

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel

WARNING_SECONDS = 5 * 60  # SES-07: warn 5 minutes before a session ends


class Classroom(TimeStampedModel):
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="classrooms"
    )
    name = models.CharField(_("class name"), max_length=100)
    description = models.CharField(_("description"), max_length=255, blank=True)
    is_archived = models.BooleanField(default=False)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def open_session(self):
        return self.sessions.filter(status=SessionStatus.OPEN).first()


class Enrollment(TimeStampedModel):
    classroom = models.ForeignKey(Classroom, on_delete=models.CASCADE, related_name="enrollments")
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="enrollments"
    )
    is_active = models.BooleanField(default=True, help_text=_("False = removed by teacher."))

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["classroom", "student"], name="unique_enrollment"),
        ]

    def __str__(self):
        return f"{self.student} in {self.classroom}"


class SessionStatus(models.TextChoices):
    OPEN = "open", _("Open")
    ENDED = "ended", _("Ended")


class ClassSession(TimeStampedModel):
    """A live play period with a room code. Not Django's login session (see GLOSSARY)."""

    classroom = models.ForeignKey(Classroom, on_delete=models.CASCADE, related_name="sessions")
    code = models.CharField(max_length=6)
    status = models.CharField(max_length=8, choices=SessionStatus.choices, default="open")
    started_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    extended_count = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["-started_at"]
        constraints = [
            # Codes only need to be unique among open sessions, so they can be reused later.
            models.UniqueConstraint(
                fields=["code"],
                condition=models.Q(status="open"),
                name="unique_open_session_code",
            ),
            # One open session per classroom at a time.
            models.UniqueConstraint(
                fields=["classroom"],
                condition=models.Q(status="open"),
                name="one_open_session_per_classroom",
            ),
        ]

    def __str__(self):
        return f"{self.classroom} · {self.code}"

    @property
    def is_open(self) -> bool:
        return self.status == SessionStatus.OPEN and timezone.now() < self.expires_at

    @property
    def seconds_left(self) -> int:
        if not self.is_open:
            return 0
        return int((self.expires_at - timezone.now()).total_seconds())

    @property
    def minutes_left(self) -> int:
        return -(-self.seconds_left // 60)  # round up

    @property
    def in_warning_window(self) -> bool:
        return self.is_open and self.seconds_left <= WARNING_SECONDS


class SessionParticipant(TimeStampedModel):
    """A student's presence in a session; feeds the teacher's live view (MON-01)."""

    session = models.ForeignKey(ClassSession, on_delete=models.CASCADE, related_name="participants")
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="participations"
    )
    last_seen_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(fields=["session", "student"], name="unique_participant"),
        ]

    def __str__(self):
        return f"{self.student} in {self.session}"

    @property
    def is_online(self) -> bool:
        # Pages poll every 5 s, so 20 s without a ping means they left or closed the tab.
        return (timezone.now() - self.last_seen_at).total_seconds() < 20
