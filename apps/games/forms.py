from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Difficulty, Operation


class StartRoundForm(forms.Form):
    operation = forms.ChoiceField(
        label=_("What do you want to practise?"),
        choices=[(Operation.ADD, _("Adding  +")), (Operation.SUB, _("Taking away  −"))],
        widget=forms.RadioSelect,
        initial=Operation.ADD,
    )
    difficulty = forms.ChoiceField(
        label=_("How hard?"),
        choices=Difficulty.choices,
        widget=forms.RadioSelect,
        initial=Difficulty.EASY,
    )
