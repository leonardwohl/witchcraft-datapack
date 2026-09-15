# Runtime Stackability Fix — Design Spec

## Problem

The Witchcraft datapack makes brewed potions stackable to 64 by overriding all 279 vanilla brewing recipes with `max_stack_size: 64` on outputs. However, potions that enter the game through non-brewing paths remain at the vanilla `max_stack_size: 1`:

- **Water bottles filled from source blocks** (right-clicking water with glass bottles)
- **Potions from loot** (buried treasure, end cities, witch drops, etc.)
- **Potions from trading** (wandering traders)
- **Potions dispensed as dropped items** (dispensers filling bottles into water)

This creates a confusing experience where some potions stack and others don't, depending on how they were obtained.

## Scope

**In scope:**
- Fix water bottles in player inventories (rapid-fill scenario)
- Fix all other potion types (regular, splash, lingering) in player inventories
- Fix dropped potion item entities (dispensers, thrown items)
- Scoreboard/storage setup on load
- Load confirmation message

**Out of scope:**
- Glass bottle → water bottle conversion (throwing bottles into water)
- Any new gameplay mechanics beyond fixing stack sizes

## Design

### Architecture Overview

Three subsystems run every game tick (20/sec), each handling a different context:

1. **Water bottles in player inventory** — clear + give (handles rapid-fill stacking)
2. **Other potions in player inventory** — item modify in-place (handles loot/trade)
3. **Dropped item entities** — data modify on entity (handles dispensers/drops)

### Why Two Approaches for Player Inventory

**Water bottles require clear+give** because players can rapidly fill bottles by holding right-click. If we only modify items in-place (changing max_stack_size from 1 to 64), each subsequent bottle the player fills arrives with vanilla max_stack_size=1 and is considered a *different item* by Minecraft's stacking logic. The bottles end up in separate slots and never merge. The only way to guarantee stacking is to remove them and give back the correct count as properly-componented items.

**Other potions can use item modify** because they're acquired one-at-a-time (opening a chest, completing a trade). There's no rapid-acquisition scenario where multiple unstackable potions arrive in the same tick. Modifying them in-place works fine — the next time the player brews the same potion (via our recipes, already stack=64), it will stack with the modified one since both now have identical components.

### File Structure

New files to add (existing recipe files unchanged):

```
data/
├── minecraft/
│   └── tags/
│       └── function/
│           ├── load.json          # calls witchcraft:load
│           └── tick.json          # calls witchcraft:tick
└── witchcraft/
    ├── function/
    │   ├── load.mcfunction            # scoreboard setup, load message
    │   ├── tick.mcfunction            # main loop, dispatches all 3 subsystems
    │   ├── fix_water_bottles.mcfunction   # clear+store+call macro
    │   └── give_water_bottles.mcfunction  # macro: give back counted bottles
    └── item_modifier/
        └── make_stackable.json        # set_components {max_stack_size: 64}
```

### Subsystem 1: Water Bottles (Clear + Give)

**tick.mcfunction** dispatches to fix_water_bottles for each player that has unstackable water bottles:

```mcfunction
execute as @a store result score @s wc.bottles run clear @s minecraft:potion[potion_contents="minecraft:water",max_stack_size=1]
execute as @a if score @s wc.bottles matches 1.. run function witchcraft:fix_water_bottles
```

**fix_water_bottles.mcfunction** moves the score into data storage and calls the macro:

```mcfunction
execute store result storage witchcraft:macro count int 1 run scoreboard players get @s wc.bottles
function witchcraft:give_water_bottles with storage witchcraft:macro
scoreboard players reset @s wc.bottles
```

**give_water_bottles.mcfunction** (macro function) gives back the exact count:

```mcfunction
$give @s minecraft:potion[max_stack_size=64,potion_contents="minecraft:water"] $(count)
```

### Subsystem 2: Other Potions (Item Modify)

**item_modifier/make_stackable.json:**

Uses `match_tool` condition to ensure only potion items are affected, even though `item modify` with a slot wildcard (`inventory.*`) applies to all slots:

```json
[
  {
    "function": "minecraft:set_components",
    "conditions": [
      {
        "condition": "minecraft:match_tool",
        "predicate": {
          "items": ["minecraft:potion", "minecraft:splash_potion", "minecraft:lingering_potion"]
        }
      }
    ],
    "components": {
      "minecraft:max_stack_size": 64
    }
  }
]
```

**tick.mcfunction** applies the modifier when unstackable potions are detected. The `if items` gate prevents running the modifier command at all on most ticks (when no unstackable potions exist), and the `match_tool` condition inside the modifier protects non-potion items from modification:

```mcfunction
# Regular potions (excluding water, handled by subsystem 1)
execute as @a if items entity @s inventory.* minecraft:potion[!max_stack_size=64,!potion_contents="minecraft:water"] run item modify entity @s inventory.* witchcraft:make_stackable

# Splash potions
execute as @a if items entity @s inventory.* minecraft:splash_potion[!max_stack_size=64] run item modify entity @s inventory.* witchcraft:make_stackable

# Lingering potions
execute as @a if items entity @s inventory.* minecraft:lingering_potion[!max_stack_size=64] run item modify entity @s inventory.* witchcraft:make_stackable
```

**Note on slot coverage:** `inventory.*` covers the main inventory grid. We also need `weapon.offhand` since players can hold potions there. The hotbar is included in `inventory.*` for the purposes of `item modify` (slots 0-8 are the hotbar within the inventory). This needs verification during implementation.

### Subsystem 3: Dropped Items (Data Modify)

**tick.mcfunction** patches dropped item entities:

```mcfunction
# Regular potions
execute as @e[type=item] if items entity @s contents minecraft:potion[!max_stack_size=64] run data modify entity @s Item.components."minecraft:max_stack_size" set value 64

# Splash potions
execute as @e[type=item] if items entity @s contents minecraft:splash_potion[!max_stack_size=64] run data modify entity @s Item.components."minecraft:max_stack_size" set value 64

# Lingering potions
execute as @e[type=item] if items entity @s contents minecraft:lingering_potion[!max_stack_size=64] run data modify entity @s Item.components."minecraft:max_stack_size" set value 64
```

### Load Function

**load.mcfunction:**

```mcfunction
scoreboard objectives add wc.bottles dummy
tellraw @a {"text":"[Witchcraft] Datapack loaded","color":"green"}
```

### Function Tags

**data/minecraft/tags/function/load.json:**
```json
{
  "values": ["witchcraft:load"]
}
```

**data/minecraft/tags/function/tick.json:**
```json
{
  "values": ["witchcraft:tick"]
}
```

## Performance

- **Water bottle check:** Runs `clear` (with count query, no actual removal until match) + scoreboard compare per player per tick. Only calls the macro function when bottles are actually found. Cheap.
- **Item modify check:** The `execute if items` predicate short-circuits — if no unstackable potions exist (the common case), the `item modify` never runs. Cost is one predicate check per player per tick per potion type (6 checks total).
- **Dropped items:** Entity selector `@e[type=item]` is already filtered by type. The `if items` predicate further narrows. Only entities matching get the `data modify`.
- **Overall:** Negligible impact for typical servers. The majority of ticks will short-circuit at the predicate checks with no mutations.

## Design Decisions

- **Use `match_tool` condition in item modifier** — protects non-potion items regardless of how `item modify` dispatches across slot wildcards.
- **Use `!max_stack_size=64` rather than `max_stack_size=1`** — safer because vanilla potions may not have an explicit max_stack_size component (they rely on the item type default of 1). Negating 64 catches anything that isn't already fixed.
- **Include offhand slot** — players can hold potions in offhand; add `weapon.offhand` checks to the item modify subsystem.
- **`clear` removes from all slots** — the give-back places items wherever Minecraft decides (typically first available slot). This may occasionally shift items from hotbar to inventory or vice versa. Acceptable tradeoff for guaranteed stacking.

## Open Questions to Verify During Implementation

1. **Exact predicate syntax for component negation** — verify `!max_stack_size=64` vs `!minecraft:max_stack_size=64` in current snapshot.
2. **Does `inventory.*` include hotbar slots (0-8)?** — if not, need separate `hotbar.*` commands.
3. **Does `match_tool` work in `item modify` context?** — if not, fall back to per-slot `execute if items` + `item modify` targeting individual slots, or use a different condition type.
4. **`potion_contents` predicate format** — verify whether `potion_contents="minecraft:water"` or `potion_contents={potion:"minecraft:water"}` is correct for the `clear`/`if items` commands.

## Testing Strategy

- Add integration test steps that verify:
  - Datapack loads without errors (existing test)
  - Function tags register correctly
  - Scoreboard objective is created on load
- Manual testing scenarios:
  - Fill bottles rapidly from water source → verify they stack
  - Dispense bottles into water → verify dropped items become stackable
  - Give self a vanilla unstackable potion → verify it gets fixed next tick
