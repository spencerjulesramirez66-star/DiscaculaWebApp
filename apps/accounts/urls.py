from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("continue/", views.after_login, name="after_login"),
    path("signup/", views.signup_choice, name="signup"),
    path("signup/teacher/", views.signup_teacher, name="signup_teacher"),
    path("signup/student/", views.signup_student, name="signup_student"),
    path("verify-email/", views.verify_email, name="verify_email"),
    path("verify-email/resend/", views.resend_verification, name="resend_verification"),
    path("password/forgot/", views.forgot_password, name="forgot_password"),
    path("password/reset/", views.reset_password, name="reset_password"),
    path("avatar/", views.avatar_builder, name="avatar"),
]
