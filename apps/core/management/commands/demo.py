"""`python manage.py demo` — ready-made accounts and history for presenting.

Creates (or resets) ONLY the demo accounts below; every other account is left alone.
Safe to run again before each rehearsal. See docs/13-presentation-guide.md.
"""

import random
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts import services as accounts
from apps.accounts.models import Role, User
from apps.classrooms import services as classrooms
from apps.classrooms.models import Classroom, ClassSession, SessionParticipant
from apps.content.services import mark_watched
from apps.games import services as games
from apps.games.models import GameRound, GameType

TEACHER_EMAIL = "teacher@demo.school"
TEACHER_PASSWORD = "blender-123"
TEACHER_NAME = "Ms. Reyes"
STUDENT_PASSWORD = "apple-123"
CLASS_NAME = "Grade 2 Math Support"

# username, full name, avatar, accessibility flags, games yesterday:
#   each game = (level, type, [tries per question]) — 1 = right first time
STUDENTS = [
    (
        "maria",
        "Maria Santos",
        {"base": "cat", "color": "orange", "hat": "crown"},
        {},
        [("easy", "add", [1, 1, 1, 1, 1]), ("easy", "sub", [3, 2, 1, 1, 1])],
    ),
    (
        "juan",
        "Juan Dela Cruz",
        {"base": "bear", "color": "blue", "accessory": "glasses"},
        {},
        [("easy", "add", [1, 1, 2, 1, 1]), ("medium", "add", [1, 2, 1, 1, 1])],
    ),
    (
        "ana",
        "Ana Lim",
        {"base": "cat", "color": "green", "hair": "tuft"},
        {"high_contrast": True, "large_text": True},
        [("easy", "add", [1, 2, 1, 1, 2])],
    ),
    # Leo is brand new: no character, no games, hasn't seen the how-to video.
    ("leo", "Leo Tan", None, {}, []),
]


class Command(BaseCommand):
    help = "Create or reset the demo teacher, class and students for presenting."

    def handle(self, *args, **options):
        with transaction.atomic():
            self._remove_old_demo()
            teacher = self._make_teacher()
            classroom = Classroom.objects.create(
                teacher=teacher, name=CLASS_NAME, description="Demo class"
            )
            students = self._make_students(teacher, classroom)
            self._play_yesterday(classroom, students)
            self._my_materials(teacher)
        self._print_logins()

    # ------------------------------------------------------------------
    def _remove_old_demo(self):
        teacher = User.objects.filter(email__iexact=TEACHER_EMAIL, role=Role.TEACHER).first()
        usernames = [s[0] for s in STUDENTS]
        clash = (
            User.objects.filter(username__in=usernames).exclude(created_by=teacher)
            if teacher
            else User.objects.filter(username__in=usernames)
        )
        if clash.exists():
            names = ", ".join(clash.values_list("username", flat=True))
            raise CommandError(
                f"These usernames already belong to real accounts: {names}. "
                "The demo won't overwrite them. Rename those accounts or use a fresh database."
            )
        if teacher:
            User.objects.filter(created_by=teacher, username__in=usernames).delete()
            teacher.delete()  # also removes the demo class, class times and question lists

    def _make_teacher(self):
        teacher = accounts.create_teacher(
            full_name=TEACHER_NAME, email=TEACHER_EMAIL, password=TEACHER_PASSWORD
        )
        teacher.email_verified = True
        teacher.save(update_fields=["email_verified"])
        return teacher

    def _make_students(self, teacher, classroom):
        made = []
        fruit_blender = GameType.objects.get(key="fruit_blender")
        for username, name, avatar, a11y, history in STUDENTS:
            student = accounts.create_student(
                full_name=name, username=username, password=STUDENT_PASSWORD, created_by=teacher
            )
            profile = student.student_profile
            if avatar:
                profile.avatar = {"pack": "default", **avatar}
            for flag, value in a11y.items():
                setattr(profile, flag, value)
            profile.save()
            classroom.enrollments.create(student=student)
            if history:  # students who played before have already seen the how-to video
                mark_watched(student, fruit_blender, None)
            made.append((student, history))
        return made

    def _play_yesterday(self, classroom, students):
        rng = random.Random(7)
        fruit_blender = GameType.objects.get(key="fruit_blender")
        session = classrooms.start_session(classroom)
        yesterday = timezone.now() - timedelta(days=1)
        for student, history in students:
            if not history:
                continue
            classrooms.join_session(student, session.code)
            participant = SessionParticipant.objects.get(session=session, student=student)
            for level, kind, tries in history:
                round_ = games.start_round(participant, fruit_blender, level, kind)
                for q, n_tries in zip(round_.questions, tries, strict=True):
                    elapsed = 0
                    for attempt in range(n_tries):
                        elapsed += rng.randint(2500, 7000)
                        wrong = attempt < n_tries - 1
                        answer = q["answer"] + (1 if wrong else 0)
                        games.record_attempt(round_, q["id"], answer, elapsed)
        classrooms.end_session(session)
        # Move it all to yesterday so today's class time starts fresh.
        ClassSession.objects.filter(pk=session.pk).update(
            started_at=yesterday,
            expires_at=yesterday + timedelta(hours=3),
            ended_at=yesterday + timedelta(hours=1),
        )
        GameRound.objects.filter(session=session).update(started_at=yesterday)
        SessionParticipant.objects.filter(session=session).update(current_game=None)

    def _my_materials(self, teacher):
        default = (
            games.visible_sets(teacher)
            .filter(owner__isnull=True, difficulty="easy", operation="add")
            .first()
        )
        if default:
            games.copy_question_set(default, teacher)

    def _print_logins(self):
        out = self.stdout
        out.write(self.style.SUCCESS("\nDemo is ready.\n"))
        out.write(f"  Teacher:  {TEACHER_EMAIL}   password: {TEACHER_PASSWORD}")
        out.write(f"  Class:    {CLASS_NAME}")
        out.write(f"  Students: maria, juan, ana, leo   password: {STUDENT_PASSWORD}")
        out.write("            (Ana has high contrast + large text; Leo is brand new)")
        out.write("\nRun it again any time to reset the demo.\n")
