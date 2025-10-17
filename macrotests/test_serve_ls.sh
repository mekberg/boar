#!/bin/bash

# Simple client-server smoke test:
# - Create a repo in the current temp dir (macrotest harness runs us under /tmp)
# - Start a TCP server on port 10002
# - Wait until it is listening
# - Run a simple 'ls' via boar://127.0.0.1:10002 and expect success

set -euo pipefail

PORT=10002
REPO="$PWD/testrepo_serve_ls"

$BOAR mkrepo "$REPO" || exit 1

# Start server in background; capture PID and ensure we clean up
$BOAR serve -p${PORT} "$REPO" >server.log 2>&1 &
SERVER_PID=$!

cleanup() {
    # Try graceful shutdown, then force if needed
    if kill -0 "$SERVER_PID" 2>/dev/null; then
        kill "$SERVER_PID" 2>/dev/null || true
        # Give it a moment to exit
        for _ in {1..20}; do
            kill -0 "$SERVER_PID" 2>/dev/null || break
            sleep 0.1
        done
        kill -9 "$SERVER_PID" 2>/dev/null || true
        wait "$SERVER_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT

# Wait for the server to be ready (max ~5s)
ready=0
for _ in {1..50}; do
    # Bash’s /dev/tcp can be used to probe if the port is listening
    if (echo >/dev/tcp/127.0.0.1/${PORT}) >/dev/null 2>&1; then
        ready=1
        break
    fi
    # Also break early if the server died
    if ! kill -0 "$SERVER_PID" 2>/dev/null; then
        break
    fi
    sleep 0.1
done

if [ "$ready" -ne 1 ]; then
    echo "Server did not start listening on port ${PORT}" >&2
    echo "Server output:" >&2
    tail -n +1 server.log >&2 || true
    exit 1
fi

# Now run a simple ls against the server; it should not fail
$BOAR --repo=boar://127.0.0.1:${PORT} ls >/dev/null || {
    echo "Client ls failed against boar://127.0.0.1:${PORT}" >&2
    exit 1
}

true
