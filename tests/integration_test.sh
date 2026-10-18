#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Auto-detect container runtime (prefer docker if daemon is running, else podman)
if command -v docker &>/dev/null && docker info &>/dev/null; then
    COMPOSE="docker compose"
elif command -v podman &>/dev/null; then
    COMPOSE="podman compose"
else
    echo "ERROR: Neither docker (running) nor podman found"
    exit 1
fi
# MC_VERSION accepts the same values as the drift check; map the aliases to itzg's names
case "${MC_VERSION:-}" in
    ""|latest-release) export MC_VERSION=LATEST ;;
    latest-snapshot) export MC_VERSION=SNAPSHOT ;;
esac

TIMEOUT=180
RCON_PASS="testing"
RCON_PORT=25575

# RCON helper: send a command to the server via docker exec + mcrcon
rcon_cmd() {
    $COMPOSE exec -T minecraft rcon-cli --password "$RCON_PASS" "$@" 2>/dev/null
}

# Podman on macOS can't mount /Volumes — copy datapack to a temp dir under /Users
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
if [[ "$REPO_ROOT" == /Volumes/* ]] && command -v podman &>/dev/null; then
    TMPDIR_BASE="${HOME}/.cache/witchcraft-test"
    mkdir -p "$TMPDIR_BASE/datapack" "$TMPDIR_BASE/server-data"
    rsync -a --delete --exclude='.git' --exclude='.venv' --exclude='tests/server-data' \
        "$REPO_ROOT/" "$TMPDIR_BASE/datapack/"
    export DATAPACK_DIR="$TMPDIR_BASE/datapack"
    export SERVER_DATA="$TMPDIR_BASE/server-data"
else
    export DATAPACK_DIR="$REPO_ROOT"
    export SERVER_DATA="$SCRIPT_DIR/server-data"
    mkdir -p "$SERVER_DATA"
fi

BOT_PIDS=()
cleanup() {
    echo "Cleaning up..."
    for pid in "${BOT_PIDS[@]}"; do kill "$pid" 2>/dev/null || true; done
    [ -n "${BOT_DIR:-}" ] && rm -rf "$BOT_DIR"
    $COMPOSE down -v 2>/dev/null || true
    # server-data may have root-owned files from the container
    rm -rf "$SCRIPT_DIR/server-data" 2>/dev/null || sudo rm -rf "$SCRIPT_DIR/server-data" 2>/dev/null || true
}
trap cleanup EXIT

echo "=== Witchcraft Datapack Integration Test ==="
echo ""

# Clean slate
$COMPOSE down -v 2>/dev/null || true

# Poll an RCON command until its output matches a regex (or time runs out)
# Usage: wait_for_rcon <seconds> <regex> <command>; prints the last output
wait_for_rcon() {
    local deadline=$((SECONDS + $1)) pattern="$2" cmd="$3" out=""
    while [ $SECONDS -lt $deadline ]; do
        out=$(rcon_cmd "$cmd" || true)
        if echo "$out" | grep -qE "$pattern"; then
            echo "$out"
            return 0
        fi
        sleep 1
    done
    echo "$out"
    return 1
}

echo "[1/10] Starting Minecraft server (${MC_VERSION})..."
$COMPOSE up -d

echo "[2/10] Waiting for server to be ready (timeout: ${TIMEOUT}s)..."
SECONDS=0
while [ $SECONDS -lt $TIMEOUT ]; do
    LOGS=$($COMPOSE logs minecraft 2>/dev/null || true)
    if echo "$LOGS" | grep -q "Done ("; then
        echo "       Server ready after ${SECONDS}s"
        break
    fi
    # A recipe that fails to parse aborts datapack loading and the server never finishes starting
    if echo "$LOGS" | grep -qE "Failed to load datapacks|Failed to start the minecraft server"; then
        echo "FAILED: Server could not load datapacks"
        echo ""
        echo "$LOGS" | grep -A10 -E "Registry loading errors|Failed to load datapacks|Failed to start" | head -40
        exit 1
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

echo "[3/10] Checking for datapack loading errors in logs..."
ERRORS=$($COMPOSE logs minecraft 2>/dev/null | grep -E "Failed to load function|Failed to parse|Couldn't parse|Couldn't load|Registry loading errors" || true)
if [ -n "$ERRORS" ]; then
    echo "FAILED: Datapack errors found in server logs:"
    echo "$ERRORS"
    exit 1
fi
echo "       No datapack errors found in logs."

echo "[4/10] Verifying datapack is enabled via RCON..."
DATAPACK_LIST=$(rcon_cmd "datapack list enabled" || true)
echo "       $DATAPACK_LIST"
if echo "$DATAPACK_LIST" | grep -q "file/witchcraft"; then
    echo "       Datapack 'file/witchcraft' confirmed enabled."
else
    echo "FAILED: Datapack 'file/witchcraft' is not enabled"
    exit 1
fi

# Keep the test chunk loaded and ticking without a player nearby
rcon_cmd "forceload add 0 0" >/dev/null

echo "[5/10] Brewing water + nether wart in a brewing stand..."
# Vanilla's recipe would produce an awkward potion without max_stack_size, so this
# proves both that our recipe loaded and that the pack.mcmeta filter blocked vanilla's
rcon_cmd 'setblock 0 -60 0 minecraft:brewing_stand{Items:[{Slot:0b,id:"minecraft:potion",count:1,components:{"minecraft:potion_contents":{potion:"minecraft:water"}}},{Slot:3b,id:"minecraft:nether_wart",count:1},{Slot:4b,id:"minecraft:blaze_powder",count:1}]} replace' >/dev/null
# Brewing takes 400 ticks; sprint through them instead of waiting 20s
rcon_cmd "tick sprint 500" >/dev/null
if BREWED=$(wait_for_rcon 30 'potion: "minecraft:awkward"' 'data get block 0 -60 0 Items[{Slot:0b}]'); then
    echo "       $BREWED"
else
    echo "FAILED: Brewing stand did not produce an awkward potion"
    echo "       Output: $BREWED"
    exit 1
fi
if echo "$BREWED" | grep -q '"minecraft:max_stack_size": 64'; then
    echo "       Brewed potion has max_stack_size 64."
else
    echo "FAILED: Brewed potion is missing max_stack_size 64 (vanilla recipe or a bad override was used)"
    exit 1
fi

echo "[6/10] Verifying load function created the scoreboard..."
SCOREBOARD_OUTPUT=$(rcon_cmd "scoreboard objectives list" || true)
if echo "$SCOREBOARD_OUTPUT" | grep -q "wc.bottles"; then
    echo "       Scoreboard objective 'wc.bottles' confirmed created."
else
    echo "FAILED: Scoreboard objective 'wc.bottles' not found"
    echo "       Output: $SCOREBOARD_OUTPUT"
    exit 1
fi

echo "[7/10] Verifying tick function patches a dropped water bottle..."
rcon_cmd 'summon item 0 -50 0 {Item:{id:"minecraft:potion",count:1,components:{"minecraft:potion_contents":{potion:"minecraft:water"}}},PickupDelay:32767,Tags:["wc_test"]}' >/dev/null
if PATCHED=$(wait_for_rcon 10 ': 64' 'data get entity @e[type=item,tag=wc_test,limit=1] Item.components."minecraft:max_stack_size"'); then
    echo "       Dropped water bottle patched to max_stack_size 64."
else
    echo "FAILED: Dropped water bottle was not made stackable"
    echo "       Output: $PATCHED"
    exit 1
fi

echo "[8/10] Brewing a pitcher plant into a Pitcher of Swiftness..."
# A raw pitcher plant takes a water bottle's place; nether wart then sugar brew it
rcon_cmd 'setblock 0 -60 0 minecraft:brewing_stand{Items:[{Slot:0b,id:"minecraft:pitcher_plant",count:1},{Slot:3b,id:"minecraft:nether_wart",count:1},{Slot:4b,id:"minecraft:blaze_powder",count:1}]} replace' >/dev/null
rcon_cmd "tick sprint 500" >/dev/null
if ! BREWED=$(wait_for_rcon 30 'potion: "minecraft:awkward"' 'data get block 0 -60 0 Items[{Slot:0b}]'); then
    echo "FAILED: Brewing stand did not brew the pitcher plant into an Awkward Pitcher"
    echo "       Output: $BREWED"
    exit 1
fi
rcon_cmd 'data modify block 0 -60 0 Items append value {Slot:3b,id:"minecraft:sugar",count:1}' >/dev/null
rcon_cmd "tick sprint 500" >/dev/null
if BREWED=$(wait_for_rcon 30 'potion: "minecraft:swiftness"' 'data get block 0 -60 0 Items[{Slot:0b}]'); then
    echo "       $BREWED"
else
    echo "FAILED: Brewing stand did not brew an Awkward Pitcher into a Pitcher of Swiftness"
    echo "       Output: $BREWED"
    exit 1
fi
if ! echo "$BREWED" | grep -q '"minecraft:item_model": "minecraft:pitcher_plant"'; then
    echo "FAILED: Pitcher of Swiftness is missing the pitcher plant model"
    exit 1
fi

# Pitchers are tested by a real player; tests/bot.py is a minimal client.
# Its packet ids come from the server JAR's own reports so it follows the version under test.
# The container owns server-data, so read the JAR through it and keep bot files in a temp dir
BOT_DIR=$(mktemp -d)
SERVER_JAR=$($COMPOSE exec -T minecraft sh -c 'ls /data/minecraft_server.*.jar' | head -n1)
$COMPOSE exec -T minecraft cat "$SERVER_JAR" > "$BOT_DIR/server.jar"
$COMPOSE exec -T minecraft sh -c "cd /tmp && java -DbundlerMainClass=net.minecraft.data.Main -jar $SERVER_JAR --reports --output /tmp/reports >/dev/null 2>&1 && cat /tmp/reports/reports/packets.json" > "$BOT_DIR/packets.json"
PROTOCOL=$(python3 -c 'import json,sys,zipfile; print(json.loads(zipfile.ZipFile(sys.argv[1]).read("version.json"))["protocol_version"])' "$BOT_DIR/server.jar")

python3 "$SCRIPT_DIR/bot.py" localhost 25565 Tester "$BOT_DIR/packets.json" "$PROTOCOL" > "$BOT_DIR/Tester.log" 2>&1 &
BOT_PIDS+=($!)
if ! wait_for_rcon 30 "Tester" "list" >/dev/null; then
    echo "FAILED: Test player could not join"
    cat "$BOT_DIR/Tester.log"
    exit 1
fi
rcon_cmd "item replace entity Tester weapon.mainhand from block 0 -60 0 container.0" >/dev/null

echo "[9/10] A pitcher can't open a vault..."
# Pitchers are trial keys underneath, but vaults only take a key with no extra components
# Put the vault two blocks from wherever the player spawned
POS=$(rcon_cmd "data get entity Tester Pos" | grep -oE '\[.*\]')
VAULT=$(python3 -c 'import math, re, sys; x, y, z = (math.floor(float(v)) for v in re.findall(r"-?[0-9.]+", sys.argv[1])); print(x + 2, y, z)' "$POS")
rcon_cmd "setblock $VAULT minecraft:vault" >/dev/null
if ! wait_for_rcon 10 "Test passed" "execute if block $VAULT minecraft:vault[vault_state=active]" >/dev/null; then
    echo "FAILED: Vault did not activate next to the test player"
    exit 1
fi
rcon_cmd "tellraw Tester \"bot:use_on $VAULT\"" >/dev/null
sleep 2
if ! rcon_cmd "execute if block $VAULT minecraft:vault[vault_state=active]" | grep -q "Test passed" \
    || ! rcon_cmd 'execute if items entity Tester weapon.mainhand minecraft:trial_key[minecraft:item_model="minecraft:pitcher_plant"]' | grep -q "Test passed"; then
    echo "FAILED: The vault took the Pitcher of Swiftness"
    cat "$BOT_DIR/Tester.log"
    exit 1
fi
echo "       The vault rejected the pitcher."

echo "[10/10] A test player drinks the Pitcher of Swiftness..."
rcon_cmd 'tellraw Tester "bot:use"' >/dev/null
if ! SPEED=$(wait_for_rcon 10 "speed" "data get entity Tester active_effects"); then
    echo "FAILED: Tester did not drink the pitcher"
    cat "$BOT_DIR/Tester.log"
    exit 1
fi
# 20:00 is 24000 ticks; allow for the time the test takes to read it back
DURATION=$(rcon_cmd 'data get entity Tester active_effects[{id:"minecraft:speed"}].duration' | grep -oE '[0-9]+$' || true)
if [ "${DURATION:-0}" -lt 23000 ] || [ "${DURATION:-0}" -gt 24000 ]; then
    echo "FAILED: Pitcher of Swiftness gave Speed for ${DURATION:-no} ticks, not 20:00"
    exit 1
fi
if ! rcon_cmd "execute if items entity Tester weapon.mainhand minecraft:pitcher_plant" | grep -q "Test passed"; then
    echo "FAILED: Drinking the pitcher did not give the pitcher plant back"
    exit 1
fi
echo "       Tester got Speed for $DURATION ticks and the pitcher plant back."

# A real trial key does open the vault, so the check in step 9 means something
rcon_cmd "item replace entity Tester weapon.mainhand with minecraft:trial_key" >/dev/null
rcon_cmd "tellraw Tester \"bot:use_on $VAULT\"" >/dev/null
if ! wait_for_rcon 10 "Test failed" "execute if block $VAULT minecraft:vault[vault_state=active]" >/dev/null; then
    echo "FAILED: A real trial key did not open the vault, so the pitcher check proves nothing"
    cat "$BOT_DIR/Tester.log"
    exit 1
fi

echo ""
echo "=== PASSED: Integration test completed successfully ==="
exit 0
