"""Seed data (CON-01): game types and default question sets.

A *data migration* runs once per database, so every fresh install (and the test DB)
starts with this content. Edit the lists below and add a NEW migration to change
defaults later — never edit this one after it has run on a real database.
"""

from django.db import migrations

GAME_TYPES = [
    # key, name, category, description, playable, order
    ("fruit_blender", "Fruit Blender", "visual", "Drag fruits into the blender", True, 1),
    ("kinesthetic_tba", "Movement game", "kinesthetic", "", False, 2),
    ("auditory_tba", "Listening game", "auditory", "", False, 3),
]

# (difficulty, operation) -> [(a, b), ...]  — ranges per docs/07-mascot-and-content.md
DEFAULT_QUESTIONS = {
    ("easy", "add"): [(1, 1), (2, 1), (2, 2), (3, 2), (1, 4)],
    ("easy", "sub"): [(2, 1), (3, 1), (4, 2), (5, 3), (5, 1)],
    ("medium", "add"): [(3, 4), (5, 2), (4, 5), (6, 3), (2, 8)],
    ("medium", "sub"): [(7, 3), (8, 5), (9, 4), (10, 6), (6, 2)],
    ("hard", "add"): [(8, 7), (9, 6), (12, 5), (11, 8), (7, 13)],
    ("hard", "sub"): [(15, 7), (17, 9), (20, 11), (14, 6), (18, 12)],
}
LABELS = {"easy": "Easy", "medium": "Medium", "hard": "Hard", "add": "adding", "sub": "taking away"}


def seed(apps, schema_editor):
    GameType = apps.get_model("games", "GameType")
    QuestionSet = apps.get_model("games", "QuestionSet")
    Question = apps.get_model("games", "Question")

    for key, name, category, description, playable, order in GAME_TYPES:
        GameType.objects.update_or_create(
            key=key,
            defaults={
                "name": name,
                "category": category,
                "description": description,
                "is_playable": playable,
                "order": order,
            },
        )

    fruit_blender = GameType.objects.get(key="fruit_blender")
    for (difficulty, operation), pairs in DEFAULT_QUESTIONS.items():
        qs, created = QuestionSet.objects.get_or_create(
            game_type=fruit_blender,
            owner=None,
            difficulty=difficulty,
            operation=operation,
            defaults={
                "title": f"Default · {LABELS[difficulty]} {LABELS[operation]}",
                "mode": "explicit",
                "question_count": len(pairs),
            },
        )
        if created:
            operator = "+" if operation == "add" else "-"
            Question.objects.bulk_create(
                Question(question_set=qs, operand_a=a, operator=operator, operand_b=b, order=i)
                for i, (a, b) in enumerate(pairs)
            )


def unseed(apps, schema_editor):
    apps.get_model("games", "QuestionSet").objects.filter(owner__isnull=True).delete()
    apps.get_model("games", "GameType").objects.filter(
        key__in=[g[0] for g in GAME_TYPES], rounds__isnull=True
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("games", "0001_initial")]

    operations = [migrations.RunPython(seed, unseed)]
