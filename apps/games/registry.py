"""Game plugin contract (ADR-0005).

Every game is:
  1. a GamePlugin subclass registered here under `key`, and
  2. a JS module at static/js/games/<key>/index.js exporting `mount(root, config, game)`.

Scoring, attempts, completion and monitoring are shared — a plugin only decides
what a round looks like and whether an answer is right.
"""

from abc import ABC, abstractmethod

_REGISTRY: dict[str, "GamePlugin"] = {}


class GamePlugin(ABC):
    key: str = ""
    category: str = ""

    @abstractmethod
    def build_round_config(self, *, questions: list[dict], difficulty: str, student) -> dict:
        """Return JSON-serialisable round data. Each question dict must keep its `id` and
        `answer`; the runtime strips `answer` before the config reaches the browser."""

    def check_answer(self, question: dict, answer) -> bool:
        try:
            return int(answer) == int(question["answer"])
        except (TypeError, ValueError, KeyError):
            return False


def register(plugin: GamePlugin) -> GamePlugin:
    if not plugin.key:
        raise ValueError("Plugin needs a key.")
    if plugin.key in _REGISTRY:
        raise ValueError(f"Game '{plugin.key}' is already registered.")
    _REGISTRY[plugin.key] = plugin
    return plugin


def get_plugin(key: str) -> GamePlugin | None:
    return _REGISTRY.get(key)


def registered_keys() -> list[str]:
    return sorted(_REGISTRY)
