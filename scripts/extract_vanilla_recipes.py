#!/usr/bin/env python3
"""Extract vanilla brewing recipes from the Minecraft server JAR and compare against our overrides.

Usage:
    python scripts/extract_vanilla_recipes.py [--version ID | --server-jar PATH] [--update]

If --server-jar is not provided, downloads the server JAR for --version from Mojang
(default: latest-release; also accepts latest-snapshot or an exact id like 26.3).

Check mode (default) fails if our recipes differ from vanilla or the server's data
pack format is outside pack.mcmeta's min_format..max_format range.

If --update is passed, regenerates our recipe overrides (and the pitcher recipes
built from them) from the extracted vanilla recipes, raises pack.mcmeta max_format to the server's data pack format if needed,
and adds the version id to the Modrinth game versions list.
"""

import json
import os
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

import generate_pitcher_recipes

VERSION_MANIFEST_URL = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
STACK_SIZE = 64
GAME_VERSIONS_FILE = Path(".github") / "modrinth-game-versions.txt"


def fetch_json(url: str) -> dict:
    with urllib.request.urlopen(url) as resp:
        return json.load(resp)


def resolve_version(version: str) -> tuple[str, str]:
    """Resolve latest-release, latest-snapshot or an exact id to (id, server JAR URL)."""
    manifest = fetch_json(VERSION_MANIFEST_URL)
    if version in ("latest-release", "latest-snapshot"):
        version = manifest["latest"][version.removeprefix("latest-")]

    entry = next((v for v in manifest["versions"] if v["id"] == version), None)
    if entry is None:
        raise ValueError(f"Unknown Minecraft version: {version}")

    details = fetch_json(entry["url"])
    return version, details["downloads"]["server"]["url"]


def download_server_jar(url: str, dest: Path) -> None:
    print(f"Downloading server JAR from {url}...")
    urllib.request.urlretrieve(url, dest)
    size_mb = dest.stat().st_size / (1024 * 1024)
    print(f"Downloaded {size_mb:.1f} MB")


def read_version_info(jar_path: Path) -> tuple[str, int]:
    """Return (version id, data pack format) from the JAR's version.json."""
    with zipfile.ZipFile(jar_path, "r") as zf:
        info = json.loads(zf.read("version.json"))

    pack_version = info["pack_version"]
    # Newer versions split into data_major/data_minor; older ones use a plain "data" int
    data_format = pack_version["data_major"] if isinstance(pack_version, dict) and "data_major" in pack_version else pack_version["data"]
    return info["id"], data_format


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
    """Load our override recipes from data/witchcraft/recipe/."""
    recipe_dir = root / "data" / "witchcraft" / "recipe"
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


def check_pack_format(root: Path, data_format: int) -> bool:
    pack = json.loads((root / "pack.mcmeta").read_text())["pack"]
    lo, hi = pack["min_format"], pack["max_format"]
    if lo <= data_format <= hi:
        print(f"PASSED: Data pack format {data_format} is within pack.mcmeta range {lo}..{hi}")
        return True
    print(f"FAILED: Data pack format {data_format} is outside pack.mcmeta range {lo}..{hi}")
    return False


def update_pack_format(root: Path, data_format: int) -> None:
    path = root / "pack.mcmeta"
    mcmeta = json.loads(path.read_text())
    if data_format > mcmeta["pack"]["max_format"]:
        print(f"Raising pack.mcmeta max_format {mcmeta['pack']['max_format']} -> {data_format}")
        mcmeta["pack"]["max_format"] = data_format
        path.write_text(json.dumps(mcmeta, indent=2) + "\n")


def add_game_version(root: Path, version_id: str) -> None:
    path = root / GAME_VERSIONS_FILE
    versions = path.read_text().split() if path.exists() else []
    if version_id not in versions:
        print(f"Adding {version_id} to {GAME_VERSIONS_FILE}")
        versions.append(version_id)
        path.write_text("\n".join(versions) + "\n")


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server-jar", type=Path, help="Path to server.jar (downloads if not provided)")
    parser.add_argument("--version", default="latest-release", help="latest-release (default), latest-snapshot, or an exact version id")
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
            version_id, url = resolve_version(args.version)
            print(f"Resolved {args.version} to {version_id}")
            download_server_jar(url, jar_path)
        except Exception as e:
            print(f"ERROR: Failed to download server JAR: {e}")
            return 1

    version_id, data_format = read_version_info(jar_path)
    print(f"Server version {version_id}, data pack format {data_format}")

    # Extract vanilla brewing recipes
    print(f"Extracting brewing recipes from {jar_path}...")
    vanilla = extract_brewing_recipes(jar_path)
    print(f"Found {len(vanilla)} vanilla brewing recipes")

    if not vanilla:
        print("ERROR: No brewing recipes found in JAR. Is this the right version?")
        return 1

    if args.update:
        # Regenerate our overrides from vanilla
        output_dir = root / "data" / "witchcraft" / "recipe"
        count = write_override_recipes(vanilla, output_dir, args.stack_size)
        print(f"Generated {count} override recipes in {output_dir}")
        generate_pitcher_recipes.main([])
        update_pack_format(root, data_format)
        add_game_version(root, version_id)
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

    format_ok = check_pack_format(root, data_format)

    if missing or extra:
        print(f"\nFAILED: Recipe coverage mismatch")
        print(f"  Run with --update to regenerate from vanilla")
        return 1

    if not format_ok:
        print(f"  Run with --update to raise max_format")
        return 1

    print("PASSED: Our overrides cover all vanilla brewing recipes exactly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
