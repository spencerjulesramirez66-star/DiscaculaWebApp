from django.urls import path

from . import views

app_name = "videos"

urlpatterns = [
    path("upload/", views.video_upload, name="upload"),
    path("<int:pk>/", views.video_view, name="view"),
    path("<int:pk>/delete/", views.video_delete, name="delete"),
]
