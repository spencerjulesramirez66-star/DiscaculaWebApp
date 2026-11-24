from django.apps import AppConfig


class GamesConfig(AppConfig):
    name = "apps.games"
    label = "games"

    def ready(self):
        # Importing the plugins package registers every game with the registry.
        from . import plugins  # noqa: F401
