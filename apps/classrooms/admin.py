from django.contrib import admin

from .models import Classroom, ClassSession, Enrollment, SessionParticipant


@admin.register(Classroom)
class ClassroomAdmin(admin.ModelAdmin):
    list_display = ("name", "teacher", "is_archived", "created_at")
    list_filter = ("is_archived",)
    search_fields = ("name", "teacher__email")


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ("student", "classroom", "is_active", "created_at")
    list_filter = ("is_active",)


@admin.register(ClassSession)
class ClassSessionAdmin(admin.ModelAdmin):
    list_display = ("code", "classroom", "status", "started_at", "expires_at", "extended_count")
    list_filter = ("status",)


@admin.register(SessionParticipant)
class SessionParticipantAdmin(admin.ModelAdmin):
    list_display = ("student", "session", "created_at", "last_seen_at")
