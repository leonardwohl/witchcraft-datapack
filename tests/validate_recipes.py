#!/usr/bin/env python3
"""Validate all brewing recipe JSON files against the schema."""

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, ValidationError


def load_schema() -> dict:
    schema_path = Path(__file__).parent / "schemas" / "brewing_recipe.json"
    with open(schema_path) as f:
        return json.load(f)


def find_recipe_files(root: Path) -> list[Path]:
    data_dir = root / "data"
    if not data_dir.exists():
        print(f"ERROR: {data_dir} does not exist")
        sys.exit(1)
    return sorted(data_dir.glob("*/recipe/*.json"))


def validate_recipes(recipe_files: list[Path], schema: dict) -> list[tuple[Path, str]]:
    validator = Draft202012Validator(schema)
    errors: list[tuple[Path, str]] = []

    for recipe_file in recipe_files:
        with open(recipe_file) as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as e:
                errors.append((recipe_file, f"Invalid JSON: {e}"))
                continue

        # Only validate files with type minecraft:brewing
        if data.get("type") != "minecraft:brewing":
            continue

        for error in validator.iter_errors(data):
            path = " -> ".join(str(p) for p in error.absolute_path) or "(root)"
            errors.append((recipe_file, f"{path}: {error.message}"))

    return errors


def main() -> int:
    root = Path(__file__).parent.parent
    schema = load_schema()
    recipe_files = find_recipe_files(root)

    if not recipe_files:
        print("WARNING: No recipe files found")
        return 0

    print(f"Validating {len(recipe_files)} recipe file(s)...")
    errors = validate_recipes(recipe_files, schema)

    if errors:
        print(f"\nFAILED: {len(errors)} error(s) found:\n")
        for filepath, message in errors:
            print(f"  {filepath.relative_to(root)}: {message}")
        return 1

    print("PASSED: All recipes are valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
