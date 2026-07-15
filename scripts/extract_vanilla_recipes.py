#!/usr/bin/env python3
"""Extract vanilla brewing recipes from the Minecraft server JAR and compare against our overrides.

Usage:
    python scripts/extract_vanilla_recipes.py [--server-jar PATH] [--update]

If --server-jar is not provided, downloads the snapshot JAR from Mojang.
If --update is passed, regenerates our recipe overrides from the extracted vanilla recipes.
"""

import json
import os
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

SERVER_JAR_URL = "https://piston-data.mojang.com/v1/objects/6cd1e711f62dc45497df6f390a9e83ba6191be41/server.jar"
STACK_SIZE = 64


def download_server_jar(dest: Path) -> None:
    print(f"Downloading server JAR from {SERVER_JAR_URL}...")
    urllib.request.urlretrieve(SERVER_JAR_URL, dest)
    size_mb = dest.stat().st_size / (1024 * 1024)
    print(f"Downloaded {size_mb:.1f} MB")


def extract_brewing_recipes(jar_path: Path) -> dict[str, dict]:
    """Extract all minecraft:brewing recipes from the server JAR.
    
    Handles the bundled JAR format (1.18+) where the actual server is nested
    inside META-INF/versions/<version>/server-<version>.jar
    """
    recipes = {}

    def scan_zip_for_recipes(zf: zipfile.ZipFile) -> None:
        for entry in zf.namelist():
            if entry.startswith("data/minecraft/recipe/") and entry.endswith(".json"):
                with zf.open(entry) as f:
                    try:
                        data = json.loads(f.read())
                    except json.JSONDecodeError:
                        continue

                    if data.get("type") == "minecraft:brewing":
                        name = Path(entry).stem
                        recipes[name] = data

    with zipfile.ZipFile(jar_path, "r") as zf:
        # Try direct extraction first
        scan_zip_for_recipes(zf)

        # If nothing found, look for nested server JAR (bundled format)
        if not recipes:
            nested_jars = [e for e in zf.namelist() if e.startswith("META-INF/versions/") and e.endswith(".jar")]
            for nested in nested_jars:
                print(f"  Checking nested JAR: {nested}")
                with zf.open(nested) as nested_f:
                    import io
                    nested_data = io.BytesIO(nested_f.read())
                    with zipfile.ZipFile(nested_data, "r") as nested_zf:
                        scan_zip_for_recipes(nested_zf)
                if recipes:
                    break

    return recipes


def add_stack_size_to_output(recipe: dict, stack_size: int) -> dict:
    """Return a copy of the recipe with max_stack_size added to the output components."""
    result = json.loads(json.dumps(recipe))  # deep copy
    output = result["output"]

    if "components" not in output:
        output["components"] = {}

    output["components"]["minecraft:max_stack_size"] = stack_size
    return result


def load_our_recipes(root: Path) -> dict[str, dict]:
    """Load our override recipes from data/minecraft/recipe/."""
    recipe_dir = root / "data" / "minecraft" / "recipe"
    recipes = {}

    if not recipe_dir.exists():
        return recipes

    for f in sorted(recipe_dir.glob("*.json")):
        with open(f) as fh:
            try:
                data = json.load(fh)
            except json.JSONDecodeError:
                continue
            if data.get("type") == "minecraft:brewing":
                recipes[f.stem] = data

    return recipes


def compare_recipes(vanilla: dict[str, dict], ours: dict[str, dict]) -> tuple[list[str], list[str]]:
    """Compare vanilla recipes against ours. Returns (missing, extra)."""
    missing = [name for name in vanilla if name not in ours]
    extra = [name for name in ours if name not in vanilla]
    return sorted(missing), sorted(extra)


def write_override_recipes(vanilla: dict[str, dict], output_dir: Path, stack_size: int) -> int:
    """Write override recipes with max_stack_size added."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Clean existing brewing recipes
    for f in output_dir.glob("*.json"):
        with open(f) as fh:
            try:
                data = json.load(fh)
                if data.get("type") == "minecraft:brewing":
                    f.unlink()
            except (json.JSONDecodeError, KeyError):
                pass

    count = 0
    for name, recipe in sorted(vanilla.items()):
        override = add_stack_size_to_output(recipe, stack_size)
        filepath = output_dir / f"{name}.json"
        with open(filepath, "w") as f:
            json.dump(override, f, indent=2)
            f.write("\n")
        count += 1

    return count


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server-jar", type=Path, help="Path to server.jar (downloads if not provided)")
    parser.add_argument("--update", action="store_true", help="Regenerate override recipes from vanilla")
    parser.add_argument("--stack-size", type=int, default=STACK_SIZE, help=f"Max stack size (default: {STACK_SIZE})")
    args = parser.parse_args()

    root = Path(__file__).parent.parent

    # Get the server JAR
    if args.server_jar:
        jar_path = args.server_jar
    else:
        tmp = tempfile.NamedTemporaryFile(suffix=".jar", delete=False)
        tmp.close()
        jar_path = Path(tmp.name)
        try:
            download_server_jar(jar_path)
        except Exception as e:
            print(f"ERROR: Failed to download server JAR: {e}")
            return 1

    # Extract vanilla brewing recipes
    print(f"Extracting brewing recipes from {jar_path}...")
    vanilla = extract_brewing_recipes(jar_path)
    print(f"Found {len(vanilla)} vanilla brewing recipes")

    if not vanilla:
        print("ERROR: No brewing recipes found in JAR. Is this the right version?")
        return 1

    if args.update:
        # Regenerate our overrides from vanilla
        output_dir = root / "data" / "minecraft" / "recipe"
        count = write_override_recipes(vanilla, output_dir, args.stack_size)
        print(f"Generated {count} override recipes in {output_dir}")
        return 0

    # Compare mode: check our recipes against vanilla
    ours = load_our_recipes(root)
    missing, extra = compare_recipes(vanilla, ours)

    if missing:
        print(f"\nMISSING: {len(missing)} vanilla recipes not in our overrides:")
        for name in missing:
            print(f"  - {name}")

    if extra:
        print(f"\nEXTRA: {len(extra)} recipes in our overrides not in vanilla:")
        for name in extra:
            print(f"  + {name}")

    if missing or extra:
        print(f"\nFAILED: Recipe coverage mismatch")
        print(f"  Run with --update to regenerate from vanilla")
        return 1

    print("PASSED: Our overrides cover all vanilla brewing recipes exactly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
