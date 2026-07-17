# Witchcraft: Stackable Potions

A Minecraft Java datapack that makes all brewed potions stackable to 64.

Targets **26.3 Snapshot 3** (Data Pack format 110).

## How it works

1. A `pack.mcmeta` filter blocks all vanilla brewing recipes from loading
2. 279 replacement recipes under the `witchcraft` namespace reproduce every vanilla brewing path, with `minecraft:max_stack_size: 64` added to each output

Potions brewed with this datapack stack to 64 in your inventory. All vanilla brewing chains work normally (water → awkward → effect → splash → lingering, modifiers, corruption, etc.).

## Installation

Copy or symlink this repo into your world's `datapacks/` folder:

```
.minecraft/saves/<world>/datapacks/witchcraft/
```

Then run `/reload` or restart the server.

## Development

Requires Python 3.12+.

```
make help            # Show all targets
make validate        # JSON schema validation (~1s)
make test            # Docker integration test (boots real MC server)
make drift-check     # Compare recipes against vanilla server JAR
make update-recipes  # Regenerate recipes from vanilla server JAR
```

### CI

GitHub Actions runs on every push:
- **Schema Validation** — checks all recipe JSON against the brewing recipe schema
- **Integration Test** — boots a snapshot server, verifies datapack loads and recipes register via RCON
- **Vanilla Drift Check** — extracts recipes from the server JAR and confirms our coverage matches 1:1

### Updating for new snapshots

When a new snapshot changes brewing recipes:

1. Update `pack.mcmeta` format versions
2. Update the server JAR URL in `scripts/extract_vanilla_recipes.py`
3. Run `make update-recipes` (or trigger the "Update Recipes from Vanilla" workflow on GitHub)
4. Commit the regenerated files
