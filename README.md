# Witchcraft: Stackable Potions

<img src="pack.png" alt="Witchcraft: Stackable Potions" width="128">

A Minecraft Java datapack that makes all brewed potions stackable to 64.

Targets **Minecraft 26.3** (Data Pack formats 110–121).

## How it works

1. A `pack.mcmeta` filter blocks all vanilla brewing recipes from loading
2. 279 replacement recipes under the `witchcraft` namespace reproduce every vanilla brewing path, with `minecraft:max_stack_size: 64` added to each output
3. A tick function fixes water bottles filled from source blocks (which bypass brewing recipes) — clearing unstackable bottles from player inventories and giving them back as stackable, and patching dropped water bottle items in-place
4. 54 pitcher recipes under `recipe/pitcher/` brew potions into a pitcher plant instead of a bottle (see below)

Potions brewed with this datapack stack to 64 in your inventory. Water bottles filled from water sources are also automatically made stackable. All vanilla brewing chains work normally (water → awkward → effect → splash → lingering, modifiers, corruption, etc.).

## Pitcher potions

A pitcher holds a lot more than a bottle, so its potions last much longer. Put a pitcher plant in a bottle slot of a brewing stand and brew it like a water bottle: nether wart makes an Awkward Pitcher, and every drinkable potion recipe works from there.

- Pitchers last **20:00**. Glowstone makes them stronger for **10:00**, and redstone turns a strong pitcher back to normal.
- Regeneration and the Turtle Master last 2:00 (1:00 when strong). Healing and Harming are instant, as in a bottle.
- Pitchers can't be made into splash or lingering potions. Gunpowder and dragon's breath do nothing to them.
- Drinking a pitcher gives the pitcher plant back, and pitchers stack to 64.

Under the hood a pitcher is a trial key with the pitcher plant's model, an enchantment glint, a drink action and the potion's contents, so no resource pack is needed. A real potion item wouldn't work: brewing recipes only check the item and potion type, so vanilla's gunpowder and redstone recipes would turn a pitcher back into a bottle. Trial keys match none of them, and vaults only accept a key with no extra components, so a pitcher can't open one. `minecraft:potion_duration_scale` stretches each potion to its pitcher duration in both the effect and the tooltip.

The pitcher recipes are generated from the potion recipes by `scripts/generate_pitcher_recipes.py` (`make pitcher-recipes`), which also holds the durations.

## Installation

### Download

Grab the latest release zip directly: [witchcraft-stackable-potions.zip](https://github.com/leonardwohl/witchcraft-datapack/releases/latest/download/witchcraft-stackable-potions.zip), or browse all versions on [GitHub Releases](https://github.com/leonardwohl/witchcraft-datapack/releases/latest).

### Singleplayer / Vanilla Server

1. Download `witchcraft-stackable-potions.zip` (or a versioned `witchcraft-stackable-potions-vX.Y.Z.zip`)
2. Place it in your world's `datapacks/` folder:
   ```
   .minecraft/saves/<world>/datapacks/witchcraft-stackable-potions.zip
   ```
3. Run `/reload` or restart the game

Alternatively, unzip and place the folder directly:
```
.minecraft/saves/<world>/datapacks/witchcraft/
```

### Docker (itzg/minecraft-server)

Use the `DATAPACKS` environment variable to auto-install from the GitHub release:

```yaml
services:
  minecraft:
    image: itzg/minecraft-server
    environment:
      EULA: "TRUE"
      VERSION: "SNAPSHOT"
      DATAPACKS: "https://github.com/leonardwohl/witchcraft-datapack/releases/latest/download/witchcraft-stackable-potions.zip"
    ports:
      - "25565:25565"
    volumes:
      - ./data:/data
```

The datapack will be downloaded and installed automatically on server startup.

## License

This work is licensed under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).

## Development

Requires Python 3.12+.

```
make help            # Show all targets
make validate        # JSON schema validation and pitcher recipe check (~1s)
make pitcher-recipes # Regenerate the pitcher recipes
make test            # Docker integration test (boots real MC server)
make drift-check     # Compare recipes and pack format against vanilla server JAR
make update-recipes  # Regenerate recipes and bump pack format from vanilla server JAR
```

`drift-check`, `update-recipes` and `test` take `MC_VERSION=latest-release` (default), `latest-snapshot`, or an exact version id like `26.3`.

### CI

GitHub Actions runs on every push:
- **Schema Validation** — checks all recipe JSON against the brewing recipe schema, and that the pitcher recipes match what the generator makes
- **Integration Test** — boots a server for the newest version in `.github/modrinth-game-versions.txt`, fails on any datapack load error, then over RCON brews a potion in a brewing stand and checks it stacks, and checks the tick function patches a dropped water bottle. It then brews a Pitcher of Swiftness, and a test player (`tests/bot.py`, a minimal client) checks that a vault refuses it and drinks it for 20 minutes of Speed
- **Vanilla Drift Check** — extracts recipes from that version's server JAR and confirms our coverage matches 1:1 and its data pack format is inside `pack.mcmeta`'s range

### Updating for new Minecraft versions

The "Update Recipes from Vanilla" workflow runs daily against the latest release and the latest snapshot. When either one changes brewing recipes or the data pack format, it opens a PR (a draft for snapshots) that regenerates the recipes and the pitcher recipes built from them, raises `max_format` in `pack.mcmeta`, and adds the version to `.github/modrinth-game-versions.txt`. You can also run it by hand with a specific version, or locally with `make update-recipes MC_VERSION=<id>`.

Snapshot PRs can add recipes for items that don't exist in the current release, so merge them only once you're ready to drop support for it.

### Releasing

Push a `vX.Y.Z` tag. The release workflow re-checks recipes against the newest version in `.github/modrinth-game-versions.txt`, then publishes the zip to GitHub Releases and Modrinth with that file as the list of supported game versions.
