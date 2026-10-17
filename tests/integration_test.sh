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

cleanup() {
    echo "Cleaning up..."
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

echo "[1/7] Starting Minecraft server (${MC_VERSION})..."
$COMPOSE up -d

echo "[2/7] Waiting for server to be ready (timeout: ${TIMEOUT}s)..."
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

echo "[3/7] Checking for datapack loading errors in logs..."
ERRORS=$($COMPOSE logs minecraft 2>/dev/null | grep -E "Failed to load function|Failed to parse|Couldn't parse|Couldn't load|Registry loading errors" || true)
if [ -n "$ERRORS" ]; then
    echo "FAILED: Datapack errors found in server logs:"
    echo "$ERRORS"
    exit 1
fi
echo "       No datapack errors found in logs."

echo "[4/7] Verifying datapack is enabled via RCON..."
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

echo "[5/7] Brewing water + nether wart in a brewing stand..."
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

echo "[6/7] Verifying load function created the scoreboard..."
SCOREBOARD_OUTPUT=$(rcon_cmd "scoreboard objectives list" || true)
if echo "$SCOREBOARD_OUTPUT" | grep -q "wc.bottles"; then
    echo "       Scoreboard objective 'wc.bottles' confirmed created."
else
    echo "FAILED: Scoreboard objective 'wc.bottles' not found"
    echo "       Output: $SCOREBOARD_OUTPUT"
    exit 1
fi

echo "[7/7] Verifying tick function patches a dropped water bottle..."
rcon_cmd 'summon item 0 -50 0 {Item:{id:"minecraft:potion",count:1,components:{"minecraft:potion_contents":{potion:"minecraft:water"}}},PickupDelay:32767,Tags:["wc_test"]}' >/dev/null
if PATCHED=$(wait_for_rcon 10 ': 64' 'data get entity @e[type=item,tag=wc_test,limit=1] Item.components."minecraft:max_stack_size"'); then
    echo "       Dropped water bottle patched to max_stack_size 64."
else
    echo "FAILED: Dropped water bottle was not made stackable"
    echo "       Output: $PATCHED"
    exit 1
fi

echo ""
echo "=== PASSED: Integration test completed successfully ==="
exit 0
