from django.urls import path

from . import views

app_name = "games"

urlpatterns = [
    path("session/<int:session_pk>/games/<slug:key>/", views.game_start, name="start"),
    path("rounds/<int:pk>/", views.round_play, name="round"),
    path("rounds/<int:pk>/attempts/", views.round_attempt, name="attempt"),
    path("rounds/<int:pk>/result/", views.round_result, name="result"),
]
