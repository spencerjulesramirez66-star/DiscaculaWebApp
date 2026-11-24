from contextlib import suppress

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from . import avatars, services
from .decorators import student_required, teacher_required
from .forms import (
    ForgotPasswordForm,
    LoginForm,
    OTPForm,
    ResetPasswordForm,
    StudentSignupForm,
    TeacherSignupForm,
)
from .models import OTPPurpose, StudentProfile

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
        try:
            services.issue_otp(user, OTPPurpose.VERIFY_EMAIL)
        except services.OTPError as exc:
            # Account exists; they can press "Send a new code" on the next page.
            messages.warning(request, _("Account created. ") + str(exc))
        else:
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


# ---------------------------------------------------------------------------
# Avatar builder (STU-01)
# ---------------------------------------------------------------------------
def _safe_next(request, fallback: str) -> str:
    target = request.POST.get("next") or request.GET.get("next") or ""
    if url_has_allowed_host_and_scheme(target, {request.get_host()}, request.is_secure()):
        return target
    return fallback


@student_required
def avatar_builder(request):
    profile, _created = StudentProfile.objects.get_or_create(user=request.user)
    manifest = avatars.pack_manifest(profile.avatar.get("pack") if profile.avatar else None)
    current = avatars.clean_avatar(profile.avatar or {}, manifest)
    next_url = _safe_next(request, reverse("play:join"))

    if request.method == "POST":
        profile.avatar = avatars.clean_avatar(request.POST.dict(), manifest)
        profile.save(update_fields=["avatar", "updated_at"])
        messages.success(request, _("Looking great!"))
        return redirect(next_url)

    layers, colors, color_key = [], {}, ""
    for layer in sorted(manifest["layers"], key=lambda item: item.get("z", 0)):
        is_color = layer.get("type") == "color"
        if is_color:
            color_key = layer["key"]
            colors = {o["id"]: o["value"] for o in layer["options"]}
        options = [
            {
                **option,
                "selected": current.get(layer["key"]) == option["id"],
                "markup": "" if is_color else avatars.layer_markup(manifest["id"], option),
            }
            for option in layer["options"]
        ]
        layers.append(
            {
                **layer,
                "options": options,
                "is_color": is_color,
                "optional": not layer.get("required"),
                "none_selected": current.get(layer["key"]) == avatars.NONE,
            }
        )
    return render(
        request,
        "accounts/avatar_builder.html",
        {
            "layers": layers,
            "state": {"choices": current, "colors": colors, "colorKey": color_key},
            "initial_color": colors.get(current.get(color_key), "currentColor"),
            "next": next_url,
            "first_time": not profile.has_avatar,
            "NONE": avatars.NONE,
        },
    )
