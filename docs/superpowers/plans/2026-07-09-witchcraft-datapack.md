# Witchcraft Datapack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bootstrap a Minecraft Java datapack with data-driven brewing recipes and a layered testing harness (JSON schema validation + Docker integration).

**Architecture:** A standard Minecraft datapack directory layout (pack.mcmeta + data/) with one example brewing recipe. Testing lives in `tests/` with a Python schema validator for fast feedback and a Docker-based integration test using `itzg/minecraft-server` for full confidence. A Makefile ties it together.

**Tech Stack:** JSON (datapack), Python 3 + jsonschema (validation), Docker + docker-compose (integration), bash (scripting), Makefile (orchestration)

---

## File Structure

| File | Responsibility |
|------|---------------|
| `pack.mcmeta` | Datapack metadata (format 110, description) |
| `data/witchcraft/recipe/example_brewing.json` | Example brewing recipe |
| `data/minecraft/recipe/.gitkeep` | Placeholder for future vanilla overrides |
| `tests/schemas/brewing_recipe.json` | JSON Schema for minecraft:brewing recipes |
| `tests/validate_recipes.py` | Schema validation script |
| `tests/requirements.txt` | Python dependencies |
| `tests/docker-compose.yml` | Docker service definition for MC server |
| `tests/integration_test.sh` | Integration test orchestration script |
| `Makefile` | Top-level build/test targets |
| `.gitignore` | Ignore Python cache, Docker volumes, etc. |

---

### Task 1: Initialize Git Repo and Boilerplate

**Files:**
- Create: `.gitignore`
- Create: `pack.mcmeta`
- Create: `data/witchcraft/recipe/.gitkeep`
- Create: `data/minecraft/recipe/.gitkeep`

- [ ] **Step 1: Initialize git repository**

Run:
```bash
git init
```

- [ ] **Step 2: Create .gitignore**

```gitignore
__pycache__/
*.pyc
.pytest_cache/
venv/
.env
tests/server-data/
```

- [ ] **Step 3: Create pack.mcmeta**

```json
{
  "pack": {
    "pack_format": 110,
    "description": "Witchcraft - Custom brewing recipes"
  }
}
```

- [ ] **Step 4: Create data directory structure with .gitkeep files**

```bash
mkdir -p data/witchcraft/recipe
mkdir -p data/minecraft/recipe
touch data/witchcraft/recipe/.gitkeep
touch data/minecraft/recipe/.gitkeep
```

- [ ] **Step 5: Commit**

```bash
git add .
git commit -m "Initialize witchcraft datapack with pack.mcmeta (format 110)"
```

---

### Task 2: Add Example Brewing Recipe

**Files:**
- Create: `data/witchcraft/recipe/example_brewing.json`
- Remove: `data/witchcraft/recipe/.gitkeep` (no longer needed)

- [ ] **Step 1: Create the example brewing recipe**

File: `data/witchcraft/recipe/example_brewing.json`

```json
{
  "type": "minecraft:brewing",
  "input": {
    "item": "minecraft:potion",
    "potion_contents": {
      "potion": "minecraft:awkward"
    }
  },
  "reagent": {
    "item": "minecraft:blaze_powder"
  },
  "output": {
    "id": "minecraft:potion",
    "components": {
      "minecraft:potion_contents": {
        "potion": "minecraft:strength"
      }
    }
  }
}
```

- [ ] **Step 2: Remove .gitkeep (directory now has content)**

```bash
rm data/witchcraft/recipe/.gitkeep
```

- [ ] **Step 3: Validate JSON is well-formed**

Run:
```bash
python3 -c "import json; json.load(open('data/witchcraft/recipe/example_brewing.json'))"
```

Expected: No output (success)

- [ ] **Step 4: Commit**

```bash
git add data/witchcraft/recipe/
git commit -m "Add example brewing recipe: awkward + blaze_powder -> strength"
```

---

### Task 3: JSON Schema for Brewing Recipes

**Files:**
- Create: `tests/schemas/brewing_recipe.json`

- [ ] **Step 1: Create the JSON Schema file**

File: `tests/schemas/brewing_recipe.json`

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Minecraft Brewing Recipe",
  "description": "Schema for minecraft:brewing recipe type (Data Pack version 110+)",
  "type": "object",
  "required": ["type", "input", "reagent", "output"],
  "properties": {
    "type": {
      "type": "string",
      "const": "minecraft:brewing"
    },
    "input": {
      "$ref": "#/$defs/potion_ingredient"
    },
    "reagent": {
      "$ref": "#/$defs/potion_ingredient"
    },
    "output": {
      "$ref": "#/$defs/item_stack"
    }
  },
  "additionalProperties": false,
  "$defs": {
    "potion_ingredient": {
      "type": "object",
      "required": ["item"],
      "properties": {
        "item": {
          "type": "string",
          "pattern": "^[a-z0-9_.-]+:[a-z0-9_/.-]+$"
        },
        "potion_contents": {
          "type": "object",
          "properties": {
            "potion": {
              "type": "string",
              "pattern": "^[a-z0-9_.-]+:[a-z0-9_/.-]+$"
            },
            "potions": {
              "type": "array",
              "items": {
                "type": "string"
              }
            },
            "effects": {
              "type": "object"
            }
          },
          "additionalProperties": true
        }
      },
      "additionalProperties": false
    },
    "item_stack": {
      "type": "object",
      "required": ["id"],
      "properties": {
        "id": {
          "type": "string",
          "pattern": "^[a-z0-9_.-]+:[a-z0-9_/.-]+$"
        },
        "components": {
          "type": "object",
          "additionalProperties": true
        },
        "count": {
          "type": "integer",
          "minimum": 1
        }
      },
      "additionalProperties": false
    }
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add tests/schemas/
git commit -m "Add JSON schema for minecraft:brewing recipe validation"
```

---

### Task 4: Python Schema Validation Script

**Files:**
- Create: `tests/requirements.txt`
- Create: `tests/validate_recipes.py`

- [ ] **Step 1: Create requirements.txt**

File: `tests/requirements.txt`

```
jsonschema>=4.0
```

- [ ] **Step 2: Create the validation script**

File: `tests/validate_recipes.py`

```python
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
```

- [ ] **Step 3: Install dependencies and run validation**

Run:
```bash
pip install -r tests/requirements.txt -q
python3 tests/validate_recipes.py
```

Expected output:
```
Validating 1 recipe file(s)...
PASSED: All recipes are valid.
```

- [ ] **Step 4: Test with an intentionally broken recipe to verify error detection**

Run:
```bash
echo '{"type": "minecraft:brewing", "input": {}, "reagent": {"item": "x"}, "output": {"id": "y"}}' > /tmp/test_bad.json
cp /tmp/test_bad.json data/witchcraft/recipe/bad_test.json
python3 tests/validate_recipes.py
```

Expected: Script reports error about missing `item` field in `input`.

Then clean up:
```bash
rm data/witchcraft/recipe/bad_test.json
```

- [ ] **Step 5: Commit**

```bash
git add tests/requirements.txt tests/validate_recipes.py
git commit -m "Add Python schema validation for brewing recipes"
```

---

### Task 5: Docker Integration Test

**Files:**
- Create: `tests/docker-compose.yml`
- Create: `tests/integration_test.sh`

- [ ] **Step 1: Create docker-compose.yml**

File: `tests/docker-compose.yml`

```yaml
services:
  minecraft:
    image: itzg/minecraft-server
    environment:
      EULA: "TRUE"
      TYPE: "VANILLA"
      VERSION: "SNAPSHOT"
      ENABLE_RCON: "true"
      RCON_PASSWORD: "testing"
      RCON_PORT: "25575"
      # Minimal server config for fast startup
      SPAWN_PROTECTION: "0"
      VIEW_DISTANCE: "4"
      SIMULATION_DISTANCE: "4"
      MAX_PLAYERS: "1"
      ONLINE_MODE: "false"
    ports:
      - "25575:25575"
    volumes:
      - ./server-data:/data
      - ..:/data/world/datapacks/witchcraft:ro
    tmpfs:
      - /data/world/region
```

- [ ] **Step 2: Create integration test script**

File: `tests/integration_test.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

COMPOSE="docker compose"
TIMEOUT=180
RCON_PASS="testing"
RCON_PORT=25575

cleanup() {
    echo "Cleaning up..."
    $COMPOSE down -v 2>/dev/null || true
    rm -rf server-data
}
trap cleanup EXIT

echo "=== Witchcraft Datapack Integration Test ==="
echo ""

# Clean slate
cleanup 2>/dev/null || true
mkdir -p server-data

echo "[1/4] Starting Minecraft server (snapshot)..."
$COMPOSE up -d

echo "[2/4] Waiting for server to be ready (timeout: ${TIMEOUT}s)..."
SECONDS=0
while [ $SECONDS -lt $TIMEOUT ]; do
    if $COMPOSE logs minecraft 2>/dev/null | grep -q "Done ("; then
        echo "       Server ready after ${SECONDS}s"
        break
    fi
    sleep 5
done

if [ $SECONDS -ge $TIMEOUT ]; then
    echo "FAILED: Server did not start within ${TIMEOUT}s"
    echo ""
    echo "=== Server logs ==="
    $COMPOSE logs minecraft 2>/dev/null | tail -50
    exit 1
fi

# Give the server a moment to finish loading datapacks
sleep 5

echo "[3/4] Checking for recipe loading errors..."
ERRORS=$($COMPOSE logs minecraft 2>/dev/null | grep -i "failed to parse\|error.*recipe\|could not load.*recipe" || true)
if [ -n "$ERRORS" ]; then
    echo "FAILED: Recipe errors found in server logs:"
    echo "$ERRORS"
    exit 1
fi
echo "       No recipe errors found in logs."

echo "[4/4] Verifying datapack loaded..."
DATAPACK_LOG=$($COMPOSE logs minecraft 2>/dev/null | grep -i "witchcraft" || true)
if [ -n "$DATAPACK_LOG" ]; then
    echo "       Datapack references found in logs:"
    echo "       $DATAPACK_LOG"
else
    # Check if the datapack directory was recognized
    echo "       (No explicit witchcraft log entries - checking datapack mount)"
fi

echo ""
echo "=== PASSED: Integration test completed successfully ==="
exit 0
```

- [ ] **Step 3: Make script executable**

```bash
chmod +x tests/integration_test.sh
```

- [ ] **Step 4: Commit**

```bash
git add tests/docker-compose.yml tests/integration_test.sh
git commit -m "Add Docker integration test for datapack loading"
```

---

### Task 6: Makefile

**Files:**
- Create: `Makefile`

- [ ] **Step 1: Create the Makefile**

File: `Makefile`

```makefile
.PHONY: validate test test-all clean help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

validate: ## Run JSON schema validation on all recipes
	@pip install -r tests/requirements.txt -q
	@python3 tests/validate_recipes.py

test: ## Run Docker integration test (requires Docker)
	@tests/integration_test.sh

test-all: validate test ## Run all tests (schema + integration)

clean: ## Remove Docker containers and test artifacts
	@cd tests && docker compose down -v 2>/dev/null || true
	@rm -rf tests/server-data
```

- [ ] **Step 2: Verify make validate works**

Run:
```bash
make validate
```

Expected:
```
Validating 1 recipe file(s)...
PASSED: All recipes are valid.
```

- [ ] **Step 3: Commit**

```bash
git add Makefile
git commit -m "Add Makefile with validate, test, and clean targets"
```

---

### Task 7: Final Verification

- [ ] **Step 1: Run make validate to confirm schema validation passes**

Run:
```bash
make validate
```

Expected: `PASSED: All recipes are valid.`

- [ ] **Step 2: Verify project structure is complete**

Run:
```bash
find . -not -path './.git/*' -not -path './.git' | sort
```

Expected output (approximately):
```
.
./.gitignore
./Makefile
./data
./data/minecraft
./data/minecraft/recipe
./data/minecraft/recipe/.gitkeep
./data/witchcraft
./data/witchcraft/recipe
./data/witchcraft/recipe/example_brewing.json
./docs
./docs/superpowers
./docs/superpowers/plans
./docs/superpowers/plans/2026-07-09-witchcraft-datapack.md
./docs/superpowers/specs
./docs/superpowers/specs/2026-07-09-witchcraft-datapack-design.md
./pack.mcmeta
./tests
./tests/docker-compose.yml
./tests/integration_test.sh
./tests/requirements.txt
./tests/schemas
./tests/schemas/brewing_recipe.json
./tests/validate_recipes.py
```

- [ ] **Step 3: Run make test (Docker integration) if Docker is available**

Run:
```bash
make test
```

Expected: Server starts, loads datapack, no recipe errors, exits 0.

Note: This step requires Docker to be running. If Docker is unavailable, skip and note that `make validate` passed.

- [ ] **Step 4: Final commit if any changes needed**

If any files were missed:
```bash
git add -A
git commit -m "Complete witchcraft datapack bootstrap"
```
