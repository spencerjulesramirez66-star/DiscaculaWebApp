from django.urls import path

from . import views_teacher as v

app_name = "teach"

urlpatterns = [
    path("", v.dashboard, name="dashboard"),
    path("classes/new/", v.classroom_create, name="classroom_create"),
    path("classes/<int:pk>/", v.classroom_detail, name="classroom_detail"),
    path("classes/<int:pk>/edit/", v.classroom_edit, name="classroom_edit"),
    path("classes/<int:pk>/archive/", v.classroom_archive, name="classroom_archive"),
    path("classes/<int:pk>/students/add/", v.students_add, name="students_add"),
    path(
        "classes/<int:pk>/students/<int:student_pk>/",
        v.student_detail,
        name="student_detail",
    ),
    path(
        "classes/<int:pk>/students/<int:student_pk>/remove/",
        v.student_remove,
        name="student_remove",
    ),
    path(
        "classes/<int:pk>/students/<int:student_pk>/restore/",
        v.student_restore,
        name="student_restore",
    ),
    path(
        "classes/<int:pk>/students/<int:student_pk>/reset-password/",
        v.student_reset_password,
        name="student_reset_password",
    ),
    path("classes/<int:pk>/sessions/start/", v.session_start, name="session_start"),
    path("sessions/<int:pk>/", v.session_detail, name="session_detail"),
    path("sessions/<int:pk>/live/", v.session_live, name="session_live"),
    path("sessions/<int:pk>/extend/", v.session_extend, name="session_extend"),
    path("sessions/<int:pk>/end/", v.session_end, name="session_end"),
]
