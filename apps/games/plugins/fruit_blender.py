"""Visual → Fruit Blender (GAM-02).

Addition a + b: drag a fruits of one kind into the blender, then b of another, Blend, pick the
answer. Subtraction a − b: the blender starts with a fruits, drag b out, Blend, pick the answer.
Sprites come from static/assets/games/fruit_blender/manifest.json.
"""

import random

from apps.core.assets import asset_url, load_manifest

from ..models import DIFFICULTY_MAX, Category
from ..questions import answer_choices
from ..registry import GamePlugin, register

ASSET_AREA = "games/fruit_blender"


class FruitBlender(GamePlugin):
    key = "fruit_blender"
    category = Category.VISUAL

    def _assets(self) -> dict:
        manifest = load_manifest(ASSET_AREA)
        return {
            "fruits": [
                {"id": f["id"], "label": f["label"], "src": asset_url(ASSET_AREA, f["src"])}
                for f in manifest["fruits"]
            ],
            "blender": {k: asset_url(ASSET_AREA, v) for k, v in manifest["blender"].items()},
            "sounds": {k: asset_url(ASSET_AREA, v) for k, v in manifest.get("sounds", {}).items()},
        }

    def build_round_config(self, *, questions, difficulty, student, rng=None) -> dict:
        rng = rng or random.Random()
        assets = self._assets()
        fruit_ids = [f["id"] for f in assets["fruits"]]
        limit = DIFFICULTY_MAX[difficulty]
        built = []
        for q in questions:
            extra = q.get("extra") or {}
            fruit_a = extra.get("fruitA") or rng.choice(fruit_ids)
            others = [f for f in fruit_ids if f != fruit_a] or fruit_ids
            fruit_b = extra.get("fruitB") or rng.choice(others)
            built.append(
                {
                    "id": q["id"],
                    "a": q["a"],
                    "op": q["op"],
                    "b": q["b"],
                    "answer": q["answer"],
                    "fruitA": fruit_a,
                    # Subtraction removes fruit from the same pile, so one kind only.
                    "fruitB": fruit_b if q["op"] == "+" else fruit_a,
                    "choices": answer_choices(q["answer"], limit, rng),
                }
            )
        return {"questions": built, "assets": assets, "maxNumber": limit}


register(FruitBlender())
