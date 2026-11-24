from django import forms
from django.db.models import Q
from django.forms import inlineformset_factory
from django.utils.translation import gettext_lazy as _

from .models import (
    ClassroomGameConfig,
    Difficulty,
    Operation,
    Operator,
    Question,
    QuestionSet,
)

MAX_QUESTIONS_PER_SET = 20


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


# ---------------------------------------------------------------------------
# Teacher question-set editor (CON-02)
# ---------------------------------------------------------------------------
class QuestionSetForm(forms.ModelForm):
    class Meta:
        model = QuestionSet
        fields = ["title"]


class QuestionForm(forms.ModelForm):
    """Two numbers. The + or − comes from the set's kind (adding / taking away)."""

    class Meta:
        model = Question
        fields = ["operand_a", "operand_b"]
        labels = {"operand_a": _("First number"), "operand_b": _("Second number")}
        widgets = {
            "operand_a": forms.NumberInput(attrs={"min": 0, "max": 20, "inputmode": "numeric"}),
            "operand_b": forms.NumberInput(attrs={"min": 0, "max": 20, "inputmode": "numeric"}),
        }

    def clean(self):
        cleaned = super().clean()
        qs = self.instance.question_set
        self.instance.operator = Operator.PLUS if qs.operation == Operation.ADD else Operator.MINUS
        return cleaned


class BaseQuestionFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        # Untouched blank rows have empty cleaned_data, so they don't count.
        kept = [f for f in self.forms if f.cleaned_data and not f.cleaned_data.get("DELETE")]
        if not kept:
            raise forms.ValidationError(_("Keep at least one question."))


QuestionFormSet = inlineformset_factory(
    QuestionSet,
    Question,
    form=QuestionForm,
    formset=BaseQuestionFormSet,
    extra=2,
    can_delete=True,
    max_num=MAX_QUESTIONS_PER_SET,
    validate_max=True,
)


# ---------------------------------------------------------------------------
# Per-classroom game settings (CON-03, CON-05)
# ---------------------------------------------------------------------------
class ClassroomGameConfigForm(forms.ModelForm):
    class Meta:
        model = ClassroomGameConfig
        fields = ["question_sets", "video"]
        widgets = {"question_sets": forms.CheckboxSelectMultiple}
        labels = {
            "question_sets": _("My question sets to use in this class"),
            "video": _("Tutorial video"),
        }
        help_texts = {
            "question_sets": _(
                "When a student picks a level and kind that matches one of these sets, "
                "it's used. Anything else uses the default questions."
            ),
        }

    def __init__(self, *args, teacher, game_type, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.content.models import Video

        self.fields["question_sets"].queryset = QuestionSet.objects.filter(
            owner=teacher, game_type=game_type
        ).order_by("difficulty", "operation", "title")
        self.fields["question_sets"].label_from_instance = lambda s: (
            f"{s.title} · {s.get_difficulty_display()} {s.get_operation_display()}"
        )
        self.fields["video"].queryset = Video.objects.filter(
            Q(owner__isnull=True) | Q(owner=teacher), game_type=game_type
        )
        self.fields["video"].empty_label = _("Default video")
        self.fields["video"].required = False
