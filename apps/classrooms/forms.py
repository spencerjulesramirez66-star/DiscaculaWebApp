from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Classroom
from .services import parse_names

MAX_BULK_STUDENTS = 60


class ClassroomForm(forms.ModelForm):
    class Meta:
        model = Classroom
        fields = ["name", "description"]
        help_texts = {
            "name": _("For example: Grade 2 Math Support"),
            "description": _("Optional. Only you see this."),
        }


class AddStudentsForm(forms.Form):
    names = forms.CharField(
        label=_("Student names"),
        widget=forms.Textarea(attrs={"rows": 6, "placeholder": "Maria Santos\nJuan Dela Cruz"}),
        help_text=_(
            "One full name per line. We create a username and an easy password for each one."
        ),
    )

    def clean_names(self):
        names = parse_names(self.cleaned_data["names"])
        if not names:
            raise forms.ValidationError(_("Type at least one name."))
        if len(names) > MAX_BULK_STUDENTS:
            raise forms.ValidationError(
                _("Add up to %(n)s students at a time.") % {"n": MAX_BULK_STUDENTS}
            )
        too_long = [n for n in names if len(n) > 150]
        if too_long:
            raise forms.ValidationError(_("Names must be 150 characters or fewer."))
        return names


class JoinForm(forms.Form):
    code = forms.CharField(
        label=_("Room code"),
        max_length=12,
        widget=forms.TextInput(
            attrs={
                "autocomplete": "off",
                "autocapitalize": "characters",
                "spellcheck": "false",
                "autofocus": True,
                "placeholder": "ABC234",
            }
        ),
    )
