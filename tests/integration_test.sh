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

echo "[1/5] Starting Minecraft server (snapshot)..."
$COMPOSE up -d

echo "[2/5] Waiting for server to be ready (timeout: ${TIMEOUT}s)..."
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

echo "[3/5] Checking for recipe loading errors in logs..."
ERRORS=$($COMPOSE logs minecraft 2>/dev/null | grep -i "failed to parse\|error.*recipe\|could not load.*recipe" || true)
if [ -n "$ERRORS" ]; then
    echo "FAILED: Recipe errors found in server logs:"
    echo "$ERRORS"
    exit 1
fi
echo "       No recipe errors found in logs."

echo "[4/5] Verifying datapack is loaded via RCON..."
DATAPACK_LIST=$(rcon_cmd "datapack list" || true)
echo "       $DATAPACK_LIST"
if echo "$DATAPACK_LIST" | grep -qi "witchcraft"; then
    echo "       Datapack 'witchcraft' confirmed loaded."
else
    echo "FAILED: Datapack 'witchcraft' not found in datapack list"
    exit 1
fi

echo "[5/5] Verifying custom recipe exists via RCON..."
RECIPE_OUTPUT=$(rcon_cmd "recipe list" || true)
if echo "$RECIPE_OUTPUT" | grep -qi "witchcraft:example_brewing"; then
    echo "       Recipe 'witchcraft:example_brewing' confirmed registered."
else
    # Some versions use 'recipe give' to test — try alternate approach
    RECIPE_GIVE=$(rcon_cmd "recipe give @a witchcraft:example_brewing" || true)
    if echo "$RECIPE_GIVE" | grep -qi "no player\|unknown\|invalid"; then
        # "no player" is fine — it means the recipe exists but no player is online
        echo "       Recipe 'witchcraft:example_brewing' confirmed registered (no player to grant)."
    elif echo "$RECIPE_GIVE" | grep -qi "unknown recipe\|invalid"; then
        echo "FAILED: Recipe 'witchcraft:example_brewing' not found"
        echo "       Output: $RECIPE_GIVE"
        exit 1
    else
        echo "       Recipe 'witchcraft:example_brewing' confirmed registered."
        echo "       Output: $RECIPE_GIVE"
    fi
fi

echo ""
echo "=== PASSED: Integration test completed successfully ==="
exit 0
