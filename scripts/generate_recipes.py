#!/usr/bin/env python3
"""Generate all vanilla Minecraft brewing recipes as JSON files with max_stack_size: 16."""

import json
import os
import shutil
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
RECIPE_DIR = PROJECT_ROOT / "data" / "minecraft" / "recipe"

CONTAINER_TYPES = ["minecraft:potion", "minecraft:splash_potion", "minecraft:lingering_potion"]


def make_recipe(input_item: str, input_potion: str, reagent: str, output_item: str, output_potion: str) -> dict:
    """Create a brewing recipe dict."""
    return {
        "type": "minecraft:brewing",
        "input": {
            "item": input_item,
            "potion_contents": {
                "potion": f"minecraft:{input_potion}",
            },
        },
        "reagent": {
            "item": f"minecraft:{reagent}",
        },
        "output": {
            "id": output_item,
            "components": {
                "minecraft:potion_contents": {
                    "potion": f"minecraft:{output_potion}",
                },
                "minecraft:max_stack_size": 16,
            },
        },
    }


def make_container_change_recipe(input_item: str, input_potion: str, reagent: str, output_item: str) -> dict:
    """Create a brewing recipe where the container type changes but potion stays the same."""
    return make_recipe(input_item, input_potion, reagent, output_item, input_potion)


def write_recipe(filename: str, recipe: dict) -> None:
    """Write a recipe to a JSON file."""
    filepath = RECIPE_DIR / filename
    with open(filepath, "w") as f:
        json.dump(recipe, f, indent=2)
        f.write("\n")


def container_prefix(container: str) -> str:
    """Get the filename prefix for a container type."""
    if container == "minecraft:potion":
        return "brewing"
    elif container == "minecraft:splash_potion":
        return "brewing_splash"
    elif container == "minecraft:lingering_potion":
        return "brewing_lingering"
    return "brewing"


def generate_all_recipes():
    """Generate all vanilla brewing recipes."""
    # Clean and recreate output directory
    if RECIPE_DIR.exists():
        shutil.rmtree(RECIPE_DIR)
    RECIPE_DIR.mkdir(parents=True)

    # =========================================================================
    # BASE BREWING (water → base potions)
    # These only apply to regular potions (splash/lingering handled by conversion)
    # =========================================================================
    base_recipes = [
        ("water", "nether_wart", "awkward"),
        ("water", "redstone", "mundane"),
        ("water", "glowstone_dust", "thick"),
        ("water", "fermented_spider_eye", "weakness"),
    ]

    for input_potion, reagent, output_potion in base_recipes:
        for container in CONTAINER_TYPES:
            prefix = container_prefix(container)
            filename = f"{prefix}_{output_potion}.json"
            recipe = make_recipe(container, input_potion, reagent, container, output_potion)
            write_recipe(filename, recipe)

    # =========================================================================
    # AWKWARD → EFFECT POTIONS
    # =========================================================================
    awkward_recipes = [
        ("golden_carrot", "night_vision"),
        ("magma_cream", "fire_resistance"),
        ("rabbit_foot", "leaping"),
        ("sugar", "swiftness"),
        ("glistering_melon_slice", "healing"),
        ("spider_eye", "poison"),
        ("ghast_tear", "regeneration"),
        ("blaze_powder", "strength"),
        ("pufferfish", "water_breathing"),
        ("turtle_helmet", "turtle_master"),
        ("phantom_membrane", "slow_falling"),
        ("breeze_rod", "wind_charged"),
        ("slime_block", "oozing"),
        ("stone", "infested"),
        ("cobweb", "weaving"),
    ]

    for reagent, output_potion in awkward_recipes:
        for container in CONTAINER_TYPES:
            prefix = container_prefix(container)
            filename = f"{prefix}_{output_potion}.json"
            recipe = make_recipe(container, "awkward", reagent, container, output_potion)
            write_recipe(filename, recipe)

    # =========================================================================
    # DURATION EXTENSION (redstone)
    # =========================================================================
    redstone_recipes = [
        ("night_vision", "long_night_vision"),
        ("fire_resistance", "long_fire_resistance"),
        ("leaping", "long_leaping"),
        ("swiftness", "long_swiftness"),
        ("poison", "long_poison"),
        ("regeneration", "long_regeneration"),
        ("strength", "long_strength"),
        ("water_breathing", "long_water_breathing"),
        ("turtle_master", "long_turtle_master"),
        ("slow_falling", "long_slow_falling"),
        ("weakness", "long_weakness"),
        ("slowness", "long_slowness"),
        ("invisibility", "long_invisibility"),
    ]

    for input_potion, output_potion in redstone_recipes:
        for container in CONTAINER_TYPES:
            prefix = container_prefix(container)
            filename = f"{prefix}_{output_potion}.json"
            recipe = make_recipe(container, input_potion, "redstone", container, output_potion)
            write_recipe(filename, recipe)

    # =========================================================================
    # AMPLIFICATION (glowstone_dust)
    # =========================================================================
    glowstone_recipes = [
        ("leaping", "strong_leaping"),
        ("swiftness", "strong_swiftness"),
        ("healing", "strong_healing"),
        ("poison", "strong_poison"),
        ("regeneration", "strong_regeneration"),
        ("strength", "strong_strength"),
        ("turtle_master", "strong_turtle_master"),
        ("harming", "strong_harming"),
        ("slowness", "strong_slowness"),
    ]

    for input_potion, output_potion in glowstone_recipes:
        for container in CONTAINER_TYPES:
            prefix = container_prefix(container)
            filename = f"{prefix}_{output_potion}.json"
            recipe = make_recipe(container, input_potion, "glowstone_dust", container, output_potion)
            write_recipe(filename, recipe)

    # =========================================================================
    # CORRUPTION (fermented_spider_eye)
    # =========================================================================
    corruption_recipes = [
        ("night_vision", "invisibility"),
        ("leaping", "slowness"),
        ("swiftness", "slowness"),
        ("healing", "harming"),
        ("poison", "harming"),
        ("water_breathing", "harming"),
        ("long_night_vision", "long_invisibility"),
        ("long_leaping", "long_slowness"),
        ("long_swiftness", "long_slowness"),
        ("long_poison", "harming"),
        ("strong_leaping", "long_slowness"),
        ("strong_swiftness", "long_slowness"),
        ("strong_healing", "strong_harming"),
        ("strong_poison", "strong_harming"),
    ]

    # Corruption recipes can have duplicate outputs (e.g., multiple paths to harming)
    # so we need unique filenames
    corruption_counter: dict[str, int] = {}
    for input_potion, output_potion in corruption_recipes:
        for container in CONTAINER_TYPES:
            prefix = container_prefix(container)
            # Use input potion in the filename to avoid collisions
            filename = f"{prefix}_{input_potion}_to_{output_potion}.json"
            recipe = make_recipe(container, input_potion, "fermented_spider_eye", container, output_potion)
            write_recipe(filename, recipe)

    # =========================================================================
    # SPLASH CONVERSION (gunpowder: potion → splash_potion)
    # =========================================================================
    # Collect all potion types that can exist
    all_potions = set()
    all_potions.add("water")
    all_potions.add("awkward")
    all_potions.add("mundane")
    all_potions.add("thick")

    # Effect potions
    for _, potion in awkward_recipes:
        all_potions.add(potion)

    # Extended potions
    for _, potion in redstone_recipes:
        all_potions.add(potion)

    # Amplified potions
    for _, potion in glowstone_recipes:
        all_potions.add(potion)

    # Corruption outputs
    for _, potion in corruption_recipes:
        all_potions.add(potion)

    # Also add the corruption inputs that weren't already added
    for potion, _ in corruption_recipes:
        all_potions.add(potion)

    for potion in sorted(all_potions):
        filename = f"brewing_splash_{potion}_from_potion.json"
        recipe = make_container_change_recipe("minecraft:potion", potion, "gunpowder", "minecraft:splash_potion")
        write_recipe(filename, recipe)

    # =========================================================================
    # LINGERING CONVERSION (dragon_breath: splash_potion → lingering_potion)
    # =========================================================================
    for potion in sorted(all_potions):
        filename = f"brewing_lingering_{potion}_from_splash.json"
        recipe = make_container_change_recipe(
            "minecraft:splash_potion", potion, "dragon_breath", "minecraft:lingering_potion"
        )
        write_recipe(filename, recipe)

    # =========================================================================
    # SPECIAL: water + gunpowder → splash water (regular potion only)
    # This is already covered by the splash conversion above for "water" potion.
    # water + dragon_breath → lingering water is also covered by lingering conversion.
    # =========================================================================

    # Count and report
    recipe_files = list(RECIPE_DIR.glob("*.json"))
    print(f"Generated {len(recipe_files)} brewing recipes in {RECIPE_DIR}")


if __name__ == "__main__":
    generate_all_recipes()
