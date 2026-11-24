from django.urls import path

from . import views_library as v

app_name = "library"

urlpatterns = [
    path("", v.library_home, name="home"),
    path("sets/<int:pk>/", v.set_view, name="set_view"),
    path("sets/<int:pk>/copy/", v.set_copy, name="set_copy"),
    path("sets/<int:pk>/edit/", v.set_edit, name="set_edit"),
    path("sets/<int:pk>/delete/", v.set_delete, name="set_delete"),
    path("classes/<int:pk>/games/<slug:key>/", v.classroom_game_settings, name="class_game"),
]
