# Witchcraft Datapack - Design Spec

**Date:** 2026-07-09
**Status:** Approved

## Overview

A Minecraft Java Edition datapack targeting the latest snapshot (26.3 Snapshot 3, Data Pack version 110.0) that adds custom brewing recipes using the new data-driven `minecraft:brewing` recipe type. The initial goal is to establish the datapack boilerplate and a layered testing harness; recipe content will be expanded later to fill vanilla brewing gaps.

## Target Version

- **Minecraft:** 26.3 Snapshot 3 (latest as of 2026-07-09)
- **Data Pack format:** 110 (`pack_format: 110`)
- **Resource Pack format:** 91 (not needed for this datapack)
- **Server JAR:** https://piston-data.mojang.com/v1/objects/6cd1e711f62dc45497df6f390a9e83ba6191be41/server.jar

## Datapack Structure

```
witchcraft-datapack/
├── pack.mcmeta
├── data/
│   ├── witchcraft/
│   │   └── recipe/
│   │       └── example_brewing.json
│   └── minecraft/
│       └── recipe/
│           (empty - for future vanilla overrides)
├── tests/
│   ├── schemas/
│   │   └── brewing_recipe.json
│   ├── validate_recipes.py
│   ├── integration_test.sh
│   ├── docker-compose.yml
│   └── requirements.txt
├── Makefile
└── docs/
    └── superpowers/
        └── specs/
            └── (this file)
```

## pack.mcmeta

```json
{
  "pack": {
    "pack_format": 110,
    "description": "Witchcraft - Custom brewing recipes"
  }
}
```

## Brewing Recipe Schema (minecraft:brewing)

Based on 26.3 Snapshot 3 changelog. Recipes go in `data/<namespace>/recipe/<name>.json`.

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | Yes | Always `"minecraft:brewing"` |
| `input` | Potion Ingredient | Yes | The item in the bottle slots |
| `reagent` | Potion Ingredient | Yes | The item in the top (ingredient) slot |
| `output` | Item Stack | Yes | The resulting item |

### Potion Ingredient format

```json
{
  "item": "minecraft:potion",
  "potion_contents": {
    "potion": "minecraft:water"
  }
}
```

- `item` (string, required): The item ID
- `potion_contents` (object, optional): A `minecraft:potion_contents` Data Component Predicate for matching specific potions

### Output Item Stack format

```json
{
  "id": "minecraft:potion",
  "components": {
    "minecraft:potion_contents": {
      "potion": "minecraft:awkward"
    }
  }
}
```

- `id` (string, required): The output item ID
- `components` (object, optional): Data components to apply to the output

### Example: Vanilla water->awkward recipe

```json
{
  "type": "minecraft:brewing",
  "input": {
    "item": "minecraft:potion",
    "potion_contents": {
      "potion": "minecraft:water"
    }
  },
  "reagent": {
    "item": "minecraft:nether_wart"
  },
  "output": {
    "id": "minecraft:potion",
    "components": {
      "minecraft:potion_contents": {
        "potion": "minecraft:awkward"
      }
    }
  }
}
```

### Example: Non-potion brewing (any items)

```json
{
  "type": "minecraft:brewing",
  "input": { "item": "minecraft:bucket" },
  "reagent": { "item": "minecraft:potent_sulfur" },
  "output": { "id": "minecraft:sulfur_cube_bucket" }
}
```

## Example Recipe (for this datapack)

One example recipe that demonstrates the feature. This modifies a vanilla brewing path by adding a new recipe (not overriding an existing one):

**File:** `data/witchcraft/recipe/example_brewing.json`

Recipe: Brew a Potion of Strength from an Awkward Potion using Blaze Powder in the reagent slot. This is a vanilla-gap recipe (vanilla requires Blaze Powder as fuel, but adding it as a direct reagent to Awkward Potion is a new path). This demonstrates our datapack adding a recipe without conflicting with existing vanilla recipes.

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

Note: We should verify this doesn't conflict with vanilla's existing strength recipe path before finalizing. If it does, we'll pick a different combination (e.g., gunpowder + potion -> splash potion as a direct conversion).

## Testing Harness

### Layer 1: JSON Schema Validation

**Purpose:** Fast feedback (<1s) during development. Catches structural errors, typos, missing fields.

**Tool:** Python 3 + `jsonschema` library

**Components:**

1. `tests/schemas/brewing_recipe.json` - JSON Schema defining the `minecraft:brewing` recipe format
2. `tests/validate_recipes.py` - Script that:
   - Walks all `data/*/recipe/*.json` files
   - Validates each against the schema
   - Reports errors with file paths and field locations
   - Exits non-zero on any failure
3. `tests/requirements.txt` - Contains `jsonschema>=4.0`

**Schema validation checks:**
- `type` field exists and equals `"minecraft:brewing"`
- `input` object has required `item` field (string)
- `input.potion_contents` is optional, if present must have valid structure
- `reagent` object has required `item` field (string)
- `reagent.potion_contents` is optional
- `output` object has required `id` field (string)
- `output.components` is optional, if present must be an object

### Layer 2: Docker Integration Test

**Purpose:** Full confidence that recipes load correctly on a real Minecraft server.

**Tool:** Docker + `itzg/minecraft-server` image + RCON

**Components:**

1. `tests/docker-compose.yml`:
   - Service: `minecraft` using `itzg/minecraft-server`
   - Environment: `VERSION=SNAPSHOT`, `TYPE=VANILLA`, `EULA=TRUE`
   - RCON enabled on port 25575
   - Datapack mounted: `../:/data/world/datapacks/witchcraft:ro`
   - Health check waiting for server ready

2. `tests/integration_test.sh`:
   - Starts docker-compose
   - Waits for server "Done" log message (timeout 120s)
   - Sends RCON command to list recipes (verifies custom recipes appear)
   - Checks server logs for "Failed to parse" or recipe-related errors
   - Tears down containers
   - Exits 0 on success, 1 on failure

**RCON validation approach:**
- Use `mcrcon` or a simple Python RCON client
- Command: `/recipe list` - verify `witchcraft:example_brewing` appears
- Parse server logs for warnings/errors about recipe parsing

### Makefile

```makefile
.PHONY: validate test test-all clean

validate:
	cd tests && pip install -r requirements.txt -q && python validate_recipes.py

test:
	cd tests && ./integration_test.sh

test-all: validate test

clean:
	cd tests && docker-compose down -v 2>/dev/null || true
```

## Namespace

- **Datapack namespace:** `witchcraft`
- **Datapack name/description:** "Witchcraft - Custom brewing recipes"

## Future Work (Out of Scope)

- Adding 10-20+ brewing recipes to fill vanilla gaps
- Resource pack additions (custom textures, models)
- CI/CD via GitHub Actions
- Potion effect customization via data components
- Recipe book integration / advancements
