from contextlib import suppress

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from . import services
from .decorators import teacher_required
from .forms import (
    ForgotPasswordForm,
    LoginForm,
    OTPForm,
    ResetPasswordForm,
    StudentSignupForm,
    TeacherSignupForm,
)
from .models import OTPPurpose

RESET_SESSION_KEY = "password_reset_identifier"


class LoginView(auth_views.LoginView):
    template_name = "accounts/login.html"
    form_class = LoginForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        response = super().form_valid(form)
        if not form.cleaned_data.get("remember_me"):
            self.request.session.set_expiry(0)  # ends when the browser closes
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["as_role"] = self.request.GET.get("as", "")
        return ctx


@login_required
def after_login(request):
    """Single landing point after login: send each role to its home."""
    user = request.user
    if user.is_teacher:
        return redirect("teach:dashboard" if user.email_verified else "accounts:verify_email")
    return redirect("play:join")


def signup_choice(request):
    if request.user.is_authenticated:
        return redirect("accounts:after_login")
    return render(request, "accounts/signup_choice.html")


def signup_teacher(request):
    form = TeacherSignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = services.create_teacher(
            full_name=form.cleaned_data["full_name"],
            email=form.cleaned_data["email"],
            password=form.cleaned_data["password1"],
        )
        login(request, user)
        services.issue_otp(user, OTPPurpose.VERIFY_EMAIL)
        messages.success(request, _("Account created. We sent a 6-digit code to your email."))
        return redirect("accounts:verify_email")
    return render(request, "accounts/signup_teacher.html", {"form": form})


def signup_student(request):
    form = StudentSignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = services.create_student(
            full_name=form.cleaned_data["full_name"],
            username=form.cleaned_data["username"],
            password=form.cleaned_data["password1"],
            email=form.cleaned_data["email"],
        )
        login(request, user)
        messages.success(request, _("Welcome! Now enter the room code from your teacher."))
        return redirect("accounts:after_login")
    return render(request, "accounts/signup_student.html", {"form": form})


@teacher_required(verified=False)
def verify_email(request):
    if request.user.email_verified:
        return redirect("accounts:after_login")
    form = OTPForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            services.verify_email(request.user, form.cleaned_data["code"])
        except services.OTPError as exc:
            form.add_error("code", str(exc))
        else:
            messages.success(request, _("Email confirmed. You can now create classrooms."))
            return redirect("accounts:after_login")
    return render(
        request,
        "accounts/verify_email.html",
        {
            "form": form,
            "resend_wait": services.seconds_until_resend(request.user, OTPPurpose.VERIFY_EMAIL),
        },
    )


@require_POST
@teacher_required(verified=False)
def resend_verification(request):
    try:
        services.issue_otp(request.user, OTPPurpose.VERIFY_EMAIL)
    except services.OTPError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, _("New code sent. Check your email."))
    return redirect("accounts:verify_email")


def forgot_password(request):
    form = ForgotPasswordForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        identifier = form.cleaned_data["identifier"].strip()
        user = services.find_user_for_reset(identifier)
        if user and user.email:
            # Cooldown errors are swallowed: an earlier code is still valid; don't leak details.
            with suppress(services.OTPError):
                services.issue_otp(user, OTPPurpose.RESET_PASSWORD)
        request.session[RESET_SESSION_KEY] = identifier
        return redirect("accounts:reset_password")
    return render(request, "accounts/forgot_password.html", {"form": form})


def reset_password(request):
    identifier = request.session.get(RESET_SESSION_KEY)
    if not identifier:
        return redirect("accounts:forgot_password")
    form = ResetPasswordForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = services.find_user_for_reset(identifier)
        try:
            if user is None or not user.email:
                raise services.OTPError(_("That code is not right."))
            services.check_otp(user, OTPPurpose.RESET_PASSWORD, form.cleaned_data["code"])
        except services.OTPError as exc:
            form.add_error("code", str(exc))
        else:
            user.set_password(form.cleaned_data["password1"])
            user.save(update_fields=["password"])
            del request.session[RESET_SESSION_KEY]
            messages.success(request, _("Password changed. You can log in now."))
            return redirect("accounts:login")
    return render(request, "accounts/reset_password.html", {"form": form})
