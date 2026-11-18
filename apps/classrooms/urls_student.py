from django.urls import path

from . import views_student as v

app_name = "play"

urlpatterns = [
    path("", v.join, name="join"),
    path("session/<int:pk>/", v.session_home, name="session"),
    path("session/<int:pk>/status/", v.session_status, name="session_status"),
]
