# Water Bottle Runtime Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add tick functions that fix unstackable water bottles in player inventories (clear+give) and on the ground as dropped items (data modify entity), so that bottles filled from water sources behave identically to those produced by brewing recipes.

**Architecture:** A `tick.mcfunction` runs every game tick. For player inventories, it clears vanilla water bottles (max_stack_size=1) and gives them back as stackable (max_stack_size=64) using a macro function for dynamic count. For dropped item entities, it patches their component data in-place. A `load.mcfunction` initializes the scoreboard objective and prints a confirmation message.

**Tech Stack:** Minecraft mcfunction (data pack format 110+), JSON function tags, scoreboard + data storage macros.

---

## File Structure

```
data/
├── minecraft/
│   └── tags/
│       └── function/
│           ├── load.json              # registers witchcraft:load
│           └── tick.json              # registers witchcraft:tick
└── witchcraft/
    └── function/
        ├── load.mcfunction            # scoreboard setup + load message
        ├── tick.mcfunction            # main loop: player inventory + dropped items
        ├── fix_water_bottles.mcfunction   # store score → call macro
        └── give_water_bottles.mcfunction  # macro: give back counted stackable bottles
```

---

### Task 1: Function Tags (load + tick registration)

**Files:**
- Create: `data/minecraft/tags/function/load.json`
- Create: `data/minecraft/tags/function/tick.json`

- [ ] **Step 1: Create the load function tag**

Create `data/minecraft/tags/function/load.json`:

```json
{
  "values": [
    "witchcraft:load"
  ]
}
```

- [ ] **Step 2: Create the tick function tag**

Create `data/minecraft/tags/function/tick.json`:

```json
{
  "values": [
    "witchcraft:tick"
  ]
}
```

- [ ] **Step 3: Commit**

```bash
git add data/minecraft/tags/function/load.json data/minecraft/tags/function/tick.json
git commit -m "Add minecraft function tags for load and tick"
```

---

### Task 2: Load Function

**Files:**
- Create: `data/witchcraft/function/load.mcfunction`

- [ ] **Step 1: Create the load function**

Create `data/witchcraft/function/load.mcfunction`:

```mcfunction
scoreboard objectives add wc.bottles dummy
tellraw @a {"text":"[Witchcraft] Datapack loaded","color":"green"}
```

This creates the scoreboard objective used to track how many unstackable water bottles were cleared from a player. The `add` command is idempotent — it does nothing if the objective already exists.

- [ ] **Step 2: Commit**

```bash
git add data/witchcraft/function/load.mcfunction
git commit -m "Add load function with scoreboard setup"
```

---

### Task 3: Water Bottle Give-Back Macro

**Files:**
- Create: `data/witchcraft/function/give_water_bottles.mcfunction`

- [ ] **Step 1: Create the macro function**

Create `data/witchcraft/function/give_water_bottles.mcfunction`:

```mcfunction
$give @s minecraft:potion[max_stack_size=64,potion_contents="minecraft:water"] $(count)
```

This is a macro function (indicated by the `$` prefix). It receives `count` from data storage and gives the executing player that many stackable water bottles. The `give` command automatically stacks items up to their max_stack_size, so giving 5 bottles results in one stack of 5.

- [ ] **Step 2: Commit**

```bash
git add data/witchcraft/function/give_water_bottles.mcfunction
git commit -m "Add give_water_bottles macro function"
```

---

### Task 4: Fix Water Bottles Helper

**Files:**
- Create: `data/witchcraft/function/fix_water_bottles.mcfunction`

- [ ] **Step 1: Create the helper function**

Create `data/witchcraft/function/fix_water_bottles.mcfunction`:

```mcfunction
execute store result storage witchcraft:macro count int 1 run scoreboard players get @s wc.bottles
function witchcraft:give_water_bottles with storage witchcraft:macro
scoreboard players reset @s wc.bottles
```

This function:
1. Copies the player's `wc.bottles` score (how many were cleared) into data storage as the `count` field
2. Calls the macro function which uses `$(count)` to give back the exact number
3. Resets the score to prevent re-triggering next tick

- [ ] **Step 2: Commit**

```bash
git add data/witchcraft/function/fix_water_bottles.mcfunction
git commit -m "Add fix_water_bottles helper (score-to-storage bridge)"
```

---

### Task 5: Tick Function (Main Loop)

**Files:**
- Create: `data/witchcraft/function/tick.mcfunction`

- [ ] **Step 1: Create the tick function**

Create `data/witchcraft/function/tick.mcfunction`:

```mcfunction
# --- Player Inventory: Clear unstackable water bottles and give back stackable ones ---
execute as @a store result score @s wc.bottles run clear @s minecraft:potion[max_stack_size=1,potion_contents="minecraft:water"]
execute as @a if score @s wc.bottles matches 1.. run function witchcraft:fix_water_bottles

# --- Dropped Items: Patch unstackable water bottle entities in-place ---
execute as @e[type=item] if items entity @s contents minecraft:potion[potion_contents="minecraft:water",!max_stack_size=64] run data modify entity @s Item.components."minecraft:max_stack_size" set value 64
```

Line-by-line explanation:

1. For every player, attempt to clear all water potions that have max_stack_size=1. The `store result score` captures how many items were removed (0 if none matched).
2. For any player whose score is 1 or more, call `fix_water_bottles` which gives them back as stackable.
3. For every dropped item entity that is a water potion without max_stack_size=64, directly patch the component on the entity. This works because `/data modify` is allowed on non-player entities. The `!max_stack_size=64` predicate means "does not have max_stack_size=64" — it catches both items with max_stack_size=1 and items with no explicit max_stack_size component (relying on the vanilla default of 1).

- [ ] **Step 2: Commit**

```bash
git add data/witchcraft/function/tick.mcfunction
git commit -m "Add tick function with water bottle fix for inventory and dropped items"
```

---

### Task 6: Schema Validation

**Files:**
- No new files — uses existing `make validate`

- [ ] **Step 1: Run schema validation to ensure nothing broke**

Run: `make validate`

Expected: All 279 recipe JSONs pass validation. The new `.mcfunction` and `.json` tag files are not covered by the recipe schema validator (it only checks `data/witchcraft/recipe/`), so this just confirms we didn't accidentally break existing files.

- [ ] **Step 2: Verify JSON syntax of new tag files**

Run:
```bash
python3 -c "import json; json.load(open('data/minecraft/tags/function/load.json')); json.load(open('data/minecraft/tags/function/tick.json')); print('OK')"
```

Expected: `OK`

---

### Task 7: Integration Test Update

**Files:**
- Modify: `tests/integration_test.sh`

- [ ] **Step 1: Add function verification to the integration test**

After the existing recipe check (step 5/5), add a new step that verifies the tick function and scoreboard are registered. Insert before the final "PASSED" message at the end of `tests/integration_test.sh`:

Add after line 115 (`fi`), before line 117 (`echo ""`):

```bash
echo "[6/6] Verifying tick functions and scoreboard..."
# Check that the scoreboard objective was created by the load function
SCOREBOARD_OUTPUT=$(rcon_cmd "scoreboard objectives list" || true)
if echo "$SCOREBOARD_OUTPUT" | grep -qi "wc.bottles"; then
    echo "       Scoreboard objective 'wc.bottles' confirmed created."
else
    echo "FAILED: Scoreboard objective 'wc.bottles' not found"
    echo "       Output: $SCOREBOARD_OUTPUT"
    exit 1
fi
```

Also update the step numbering in the existing test from `[1/5]`...`[5/5]` to `[1/6]`...`[5/6]`.

- [ ] **Step 2: Commit**

```bash
git add tests/integration_test.sh
git commit -m "Add scoreboard verification to integration test"
```

---

### Task 8: Update README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update the "How it works" section**

Replace the existing "How it works" section (lines 9-14) with:

```markdown
## How it works

1. A `pack.mcmeta` filter blocks all vanilla brewing recipes from loading
2. 279 replacement recipes under the `witchcraft` namespace reproduce every vanilla brewing path, with `minecraft:max_stack_size: 64` added to each output
3. A tick function fixes water bottles filled from source blocks (which bypass brewing recipes) — clearing unstackable bottles from player inventories and giving them back as stackable, and patching dropped water bottle items in-place

Potions brewed with this datapack stack to 64 in your inventory. Water bottles filled from water sources are also automatically made stackable. All vanilla brewing chains work normally (water → awkward → effect → splash → lingering, modifiers, corruption, etc.).
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "Update README with tick function documentation"
```

---

## Verification Checklist

After all tasks are complete:

1. `make validate` passes (recipe schemas still valid)
2. JSON tag files parse without error
3. `make test` passes (integration test with new scoreboard check)
4. Manual in-game test: fill bottles from water source rapidly → they stack to 64
5. Manual in-game test: dispenser fills bottle → dropped item is stackable
