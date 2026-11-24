"""Plain names for the ready-made question lists: "Default · Easy adding" → "Easy adding"."""

from django.db import migrations

PREFIX = "Default · "


def forwards(apps, schema_editor):
    QuestionSet = apps.get_model("games", "QuestionSet")
    for qs in QuestionSet.objects.filter(owner__isnull=True, title__startswith=PREFIX):
        qs.title = qs.title.removeprefix(PREFIX).capitalize()
        qs.save(update_fields=["title"])


def backwards(apps, schema_editor):
    QuestionSet = apps.get_model("games", "QuestionSet")
    for qs in QuestionSet.objects.filter(owner__isnull=True).exclude(title__startswith=PREFIX):
        qs.title = PREFIX + qs.title
        qs.save(update_fields=["title"])


class Migration(migrations.Migration):
    dependencies = [("games", "0003_classroomgameconfig")]

    operations = [migrations.RunPython(forwards, backwards)]
