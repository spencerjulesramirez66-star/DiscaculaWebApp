from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import AuthenticationForm
from django.utils.translation import gettext_lazy as _

from .models import Role, User, username_validator


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        label=_("Email or username"),
        widget=forms.TextInput(attrs={"autofocus": True, "autocomplete": "username"}),
        help_text=_("Teachers: your email. Students: your username."),
    )
    remember_me = forms.BooleanField(
        label=_("Keep me logged in on this device"), required=False, initial=True
    )

    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": _("That login and password don't match. Check them and try again."),
    }


class _PasswordPairMixin(forms.Form):
    password1 = forms.CharField(
        label=_("Password"),
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text=_("At least 8 characters. A few short words with a number works well."),
    )
    password2 = forms.CharField(
        label=_("Type the password again"),
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    def _candidate_user(self) -> User:
        return User(
            username=self.cleaned_data.get("username", ""),
            email=self.cleaned_data.get("email", ""),
            full_name=self.cleaned_data.get("full_name", ""),
        )

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", _("The two passwords don't match."))
        elif p1:
            try:
                password_validation.validate_password(p1, self._candidate_user())
            except forms.ValidationError as exc:
                self.add_error("password1", exc)
        return cleaned


class TeacherSignupForm(_PasswordPairMixin):
    field_order = ["full_name", "email", "password1", "password2"]

    full_name = forms.CharField(label=_("Full name"), max_length=150)
    email = forms.EmailField(
        label=_("Email"),
        help_text=_("You'll log in with this. We'll send a 6-digit code to confirm it."),
        widget=forms.EmailInput(attrs={"autocomplete": "email"}),
    )

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email, role=Role.TEACHER).exists():
            raise forms.ValidationError(_("A teacher account with this email already exists."))
        return email


class StudentSignupForm(_PasswordPairMixin):
    field_order = ["full_name", "username", "password1", "password2", "email"]

    full_name = forms.CharField(label=_("Full name"), max_length=150)
    username = forms.CharField(
        label=_("Username"),
        max_length=150,
        validators=[username_validator],
        help_text=_("What you'll type to log in. Letters, numbers, dots and dashes."),
        widget=forms.TextInput(attrs={"autocomplete": "username", "autocapitalize": "none"}),
    )
    email = forms.EmailField(
        label=_("Email (optional)"),
        required=False,
        help_text=_("A parent's email is fine. Only used if you forget your password."),
    )

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError(_("That username is taken. Try adding a number."))
        return username


class OTPForm(forms.Form):
    code = forms.RegexField(
        label=_("6-digit code"),
        regex=r"^\s*\d{6}\s*$",
        error_messages={"invalid": _("Enter the 6 numbers from the email.")},
        widget=forms.TextInput(
            attrs={"inputmode": "numeric", "autocomplete": "one-time-code", "maxlength": 6}
        ),
    )


class ForgotPasswordForm(forms.Form):
    identifier = forms.CharField(
        label=_("Username or teacher email"),
        widget=forms.TextInput(attrs={"autocapitalize": "none"}),
    )


class ResetPasswordForm(_PasswordPairMixin, OTPForm):
    field_order = ["code", "password1", "password2"]
