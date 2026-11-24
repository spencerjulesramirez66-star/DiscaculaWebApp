"""Seed data (CON-04): one default tutorial video per playable game.

The files live under static/ so they ship with the app. Replace the placeholder by dropping a
real video at the same path (see docs/10-assets-guide.md) — no migration needed. If the file
is missing, the tutorial screen shows written steps instead.
"""

from django.db import migrations

DEFAULT_VIDEOS = [
    # game key, title, video path, captions path (both relative to static/)
    (
        "fruit_blender",
        "How to play Fruit Blender",
        "assets/videos/placeholders/fruit_blender-tutorial.webm",
        "assets/videos/placeholders/fruit_blender-tutorial.vtt",
    ),
]


def seed(apps, schema_editor):
    GameType = apps.get_model("games", "GameType")
    Video = apps.get_model("content", "Video")
    for key, title, video_path, captions_path in DEFAULT_VIDEOS:
        game = GameType.objects.filter(key=key).first()
        if game is None:
            continue
        Video.objects.get_or_create(
            game_type=game,
            owner=None,
            static_path=video_path,
            defaults={"title": title, "static_captions_path": captions_path},
        )


def unseed(apps, schema_editor):
    apps.get_model("content", "Video").objects.filter(owner__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("content", "0001_initial"),
        ("games", "0002_seed_default_content"),
    ]

    operations = [migrations.RunPython(seed, unseed)]
