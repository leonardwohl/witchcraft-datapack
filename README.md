# Witchcraft: Stackable Potions

<img src="pack.png" alt="Witchcraft: Stackable Potions" width="128">

A Minecraft Java datapack that makes all brewed potions stackable to 64.

Targets **Minecraft 26.3** (Data Pack formats 110–121).

## How it works

1. A `pack.mcmeta` filter blocks all vanilla brewing recipes from loading
2. 279 replacement recipes under the `witchcraft` namespace reproduce every vanilla brewing path, with `minecraft:max_stack_size: 64` added to each output
3. A tick function fixes water bottles filled from source blocks (which bypass brewing recipes) — clearing unstackable bottles from player inventories and giving them back as stackable, and patching dropped water bottle items in-place

Potions brewed with this datapack stack to 64 in your inventory. Water bottles filled from water sources are also automatically made stackable. All vanilla brewing chains work normally (water → awkward → effect → splash → lingering, modifiers, corruption, etc.).

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
make validate        # JSON schema validation (~1s)
make test            # Docker integration test (boots real MC server)
make drift-check     # Compare recipes and pack format against vanilla server JAR
make update-recipes  # Regenerate recipes and bump pack format from vanilla server JAR
```

`drift-check`, `update-recipes` and `test` take `MC_VERSION=latest-release` (default), `latest-snapshot`, or an exact version id like `26.3`.

### CI

GitHub Actions runs on every push:
- **Schema Validation** — checks all recipe JSON against the brewing recipe schema
- **Integration Test** — boots a server for the newest version in `.github/modrinth-game-versions.txt`, verifies datapack loads and recipes register via RCON
- **Vanilla Drift Check** — extracts recipes from that version's server JAR and confirms our coverage matches 1:1 and its data pack format is inside `pack.mcmeta`'s range

### Updating for new Minecraft versions

The "Update Recipes from Vanilla" workflow runs daily against the latest release and the latest snapshot. When either one changes brewing recipes or the data pack format, it opens a PR (a draft for snapshots) that regenerates the recipes, raises `max_format` in `pack.mcmeta`, and adds the version to `.github/modrinth-game-versions.txt`. You can also run it by hand with a specific version, or locally with `make update-recipes MC_VERSION=<id>`.

Snapshot PRs can add recipes for items that don't exist in the current release, so merge them only once you're ready to drop support for it.

### Releasing

Push a `vX.Y.Z` tag. The release workflow re-checks recipes against the newest version in `.github/modrinth-game-versions.txt`, then publishes the zip to GitHub Releases and Modrinth with that file as the list of supported game versions.
