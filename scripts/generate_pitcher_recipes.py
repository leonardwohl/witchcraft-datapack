#!/usr/bin/env python3
"""Generate the pitcher potion recipes from our drinkable potion recipes.

Usage:
    python scripts/generate_pitcher_recipes.py [--check]

A pitcher plant goes in a bottle slot like a water bottle and brews into a pitcher
potion: a trial key with the pitcher plant's model, an enchantment glint, a drink
action and the potion's contents. Trial keys never match vanilla's potion recipes,
so gunpowder and dragon's breath do nothing to a pitcher, and stack to 64 already.
(Vaults only take a trial key with no extra components, so pitchers can't open one.)

Every vanilla potion -> potion recipe gets a pitcher version, except redstone ones:
pitchers already last 20 minutes, and glowstone makes them stronger for 10 minutes.
Redstone on a strong pitcher turns it back to normal strength instead.
minecraft:potion_duration_scale stretches each potion to its pitcher duration, in
both the effect and the tooltip.

--check fails if the recipes on disk differ from what would be generated.
"""

import json
import math
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
SOURCE_DIR = ROOT / "data" / "witchcraft" / "recipe"
OUTPUT_DIR = SOURCE_DIR / "pitcher"

PITCHER = "minecraft:pitcher_plant"
PITCHER_POTION = "minecraft:trial_key"

MINUTE = 20 * 60
# Pitcher durations in ticks for (normal, strong) potions
DEFAULT_DURATION = (20 * MINUTE, 10 * MINUTE)
DURATIONS = {
    "regeneration": (2 * MINUTE, 1 * MINUTE),
    "turtle_master": (2 * MINUTE, 1 * MINUTE),
}

# Vanilla effect durations in ticks (net.minecraft.world.item.alchemy.Potions).
# None means the potion has no lasting effect, so its duration isn't scaled.
VANILLA_DURATIONS = {
    "water": None, "mundane": None, "thick": None, "awkward": None,
    "healing": None, "strong_healing": None, "harming": None, "strong_harming": None,
    "night_vision": 3600, "invisibility": 3600, "fire_resistance": 3600,
    "water_breathing": 3600, "wind_charged": 3600, "weaving": 3600,
    "oozing": 3600, "infested": 3600,
    "leaping": 3600, "strong_leaping": 1800,
    "swiftness": 3600, "strong_swiftness": 1800,
    "strength": 3600, "strong_strength": 1800,
    "slowness": 1800, "strong_slowness": 400,
    "turtle_master": 400, "strong_turtle_master": 400,
    "poison": 900, "strong_poison": 432,
    "regeneration": 900, "strong_regeneration": 450,
    "weakness": 1800, "slow_falling": 1800,
}

NAMES = {
    "water": "Water Pitcher", "mundane": "Mundane Pitcher",
    "thick": "Thick Pitcher", "awkward": "Awkward Pitcher",
    "turtle_master": "Pitcher of the Turtle Master",
    "wind_charged": "Pitcher of Wind Charging",
    "infested": "Pitcher of Infestation",
}


def base_name(potion: str) -> str:
    return potion.removeprefix("strong_")


def pitcher_name(potion: str) -> str:
    name = base_name(potion)
    return NAMES.get(name) or "Pitcher of " + name.replace("_", " ").title()


def f32(x: float) -> float:
    return struct.unpack("f", struct.pack("f", x))[0]


def duration_scale(vanilla: int, target: int) -> float:
    """Shortest scale that the game turns into exactly `target` ticks.

    The game stores the scale as a float and floors vanilla * scale in float math,
    so 20/3 written plainly would give 23999 ticks (19:59) instead of 24000.
    """
    for digits in range(1, 10):
        scale = math.ceil(target / vanilla * 10**digits) / 10**digits
        if int(f32(vanilla * f32(scale))) == target:
            return scale
    raise ValueError(f"No float scale turns {vanilla} ticks into {target}")


def pitcher_output(potion: str) -> dict:
    if potion not in VANILLA_DURATIONS:
        sys.exit(f"ERROR: No vanilla duration known for minecraft:{potion}; add it to VANILLA_DURATIONS")

    components = {
        "minecraft:potion_contents": {"potion": f"minecraft:{potion}"},
    }
    vanilla = VANILLA_DURATIONS[potion]
    if vanilla is not None:
        normal, strong = DURATIONS.get(base_name(potion), DEFAULT_DURATION)
        target = strong if potion.startswith("strong_") else normal
        components["minecraft:potion_duration_scale"] = duration_scale(vanilla, target)
    components |= {
        "minecraft:item_model": PITCHER,
        "minecraft:item_name": {
            "translate": f"item.witchcraft.pitcher.effect.{base_name(potion)}",
            "fallback": pitcher_name(potion),
        },
        "minecraft:enchantment_glint_override": True,
        "minecraft:consumable": {
            "animation": "drink",
            "sound": "minecraft:entity.generic.drink",
            "has_consume_particles": False,
        },
        "minecraft:use_remainder": {"id": PITCHER},
    }
    return {"components": components, "id": PITCHER_POTION}


def pitcher_input(potion: str) -> dict:
    # An empty pitcher plant takes the place of a water bottle
    if potion == "water":
        return {"item": PITCHER}
    return {"item": PITCHER_POTION, "potion_contents": {"potions": f"minecraft:{potion}"}}


def recipe(input_potion: str, reagent: dict, output_potion: str) -> dict:
    return {
        "type": "minecraft:brewing",
        "input": pitcher_input(input_potion),
        "output": pitcher_output(output_potion),
        "reagent": reagent,
    }


def potion_id(stack: dict, key: str) -> str:
    return stack[key]["potion" if key == "minecraft:potion_contents" else "potions"].removeprefix("minecraft:")


def generate() -> dict[str, dict]:
    recipes = {}
    strong = set()
    for f in sorted(SOURCE_DIR.glob("*.json")):
        source = json.loads(f.read_text())
        if source.get("type") != "minecraft:brewing":
            continue
        if source["input"]["item"] != "minecraft:potion" or source["output"]["id"] != "minecraft:potion":
            continue
        input_potion = potion_id(source["input"], "potion_contents")
        output_potion = potion_id(source["output"]["components"], "minecraft:potion_contents")
        if source["reagent"] == {"item": "minecraft:redstone"} or output_potion.startswith("long_") or input_potion.startswith("long_"):
            continue
        recipes[f.stem.removeprefix("potion_")] = recipe(input_potion, source["reagent"], output_potion)
        if output_potion.startswith("strong_"):
            strong.add(output_potion)

    for potion in sorted(strong):
        recipes[f"{potion}_redstone"] = recipe(potion, {"item": "minecraft:redstone"}, base_name(potion))
    return recipes


def main(args: list[str]) -> int:
    check = "--check" in args
    recipes = generate()
    expected = {name: json.dumps(r, indent=2) + "\n" for name, r in recipes.items()}
    existing = {f.stem: f.read_text() for f in OUTPUT_DIR.glob("*.json")} if OUTPUT_DIR.exists() else {}

    if check:
        stale = sorted(n for n in expected.keys() | existing.keys() if expected.get(n) != existing.get(n))
        if stale:
            print(f"FAILED: {len(stale)} pitcher recipe(s) out of date: {', '.join(stale)}")
            print("  Run scripts/generate_pitcher_recipes.py to regenerate")
            return 1
        print(f"PASSED: {len(expected)} pitcher recipes are up to date.")
        return 0

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for name in existing.keys() - expected.keys():
        (OUTPUT_DIR / f"{name}.json").unlink()
    for name, text in expected.items():
        (OUTPUT_DIR / f"{name}.json").write_text(text)
    print(f"Generated {len(expected)} pitcher recipes in {OUTPUT_DIR.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
