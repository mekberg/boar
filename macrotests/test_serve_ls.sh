#!/bin/bash

# Client-server tests over TCP:
# - Create a repo in the current temp dir (macrotest harness runs us under /tmp)
# - Start TCP servers in the different security modes
# - Check that clients get access exactly when they should

set -uo pipefail

REPO="$PWD/testrepo_serve_ls"
SERVER_PID=""

$BOAR mkrepo "$REPO" || exit 1
$BOAR --repo="$REPO" mksession TestSession || exit 1

if ! $PYTHON_BINARY -c "import nacl.bindings" 2>/dev/null; then
    HAVE_CRYPTO=0
    echo "PyNaCl is not installed, skipping the encrypted connection tests"
else
    HAVE_CRYPTO=1
fi

unset BOAR_KEYFILE BOAR_ALLOW_INSECURE

stop_server() {
    # Try graceful shutdown, then force if needed
    if [ -n "$SERVER_PID" ] && kill -0 "$SERVER_PID" 2>/dev/null; then
        kill "$SERVER_PID" 2>/dev/null || true
        # Give it a moment to exit
        for _ in {1..20}; do
            kill -0 "$SERVER_PID" 2>/dev/null || break
            sleep 0.1
        done
        kill -9 "$SERVER_PID" 2>/dev/null || true
        wait "$SERVER_PID" 2>/dev/null || true
    fi
    SERVER_PID=""
}
trap stop_server EXIT

start_server() { # port, serve options...
    local port=$1
    shift
    $BOAR serve -p${port} "$@" "$REPO" >server.log 2>&1 &
    SERVER_PID=$!
    # Wait for the server to be ready (max ~5s)
    for _ in {1..50}; do
        # Bash’s /dev/tcp can be used to probe if the port is listening
        if (echo >/dev/tcp/127.0.0.1/${port}) >/dev/null 2>&1; then
            return
        fi
        # Also break early if the server died
        kill -0 "$SERVER_PID" 2>/dev/null || break
        sleep 0.1
    done
    echo "Server did not start listening on port ${port}" >&2
    echo "Server output:" >&2
    cat server.log >&2
    exit 1
}

expect_ok() { # description, command...
    local desc=$1
    shift
    "$@" >client.log 2>&1 || {
        echo "Failed (should have succeeded): $desc" >&2
        cat client.log server.log >&2
        exit 1
    }
    grep -q TestSession client.log || { echo "Unexpected output: $desc" >&2; cat client.log >&2; exit 1; }
}

expect_fail() { # description, expected message, command...
    local desc=$1 msg=$2
    shift 2
    if "$@" >client.log 2>&1; then
        echo "Succeeded (should have failed): $desc" >&2
        cat client.log >&2
        exit 1
    fi
    grep -q "$msg" client.log || { echo "Expected message '$msg' missing: $desc" >&2; cat client.log >&2; exit 1; }
    grep -q TestSession client.log && { echo "Repository contents leaked: $desc" >&2; exit 1; }
    grep -q Traceback client.log && { echo "Unclean failure: $desc" >&2; cat client.log >&2; exit 1; }
    return 0
}

# A stand-in for a boar client from before encryption was introduced
cat >legacy_client.py <<PYEOF
import sys, socket
sys.path.insert(0, "$BOARTESTHOME/..")
import client, boar_exceptions
s = socket.create_connection(("127.0.0.1", int(sys.argv[1])))
try:
    front = client.create_boar_proxy(s.makefile(mode="wb"), s.makefile(mode="rb")).front
except boar_exceptions.UserError as e:
    sys.exit("ERROR: %s" % e)
print(front.get_session_names())
PYEOF

#
# A server must not start unprotected unless explicitly told to
#
expect_fail "serve without key" "You must specify a key file" $BOAR serve -p10002 "$REPO"

#
# Server with no security at all
#
PORT=10002
URL=boar://127.0.0.1:${PORT}
start_server $PORT --allow-insecure
grep -q "WARNING: This server has no authentication or encryption" server.log || { echo "Missing server warning" >&2; exit 1; }
expect_fail "no key, insecure not allowed by client" "requires its key" $BOAR --repo=$URL sessions
expect_ok "insecure client, insecure server" env BOAR_ALLOW_INSECURE=1 $BOAR --repo=$URL sessions
grep -q "INSECURE" client.log || { echo "Missing client warning" >&2; exit 1; }
expect_ok "legacy client, insecure server" $PYTHON_BINARY legacy_client.py $PORT

[ $HAVE_CRYPTO = 1 ] || exit 0

$BOAR mkkey key.txt || exit 1
$BOAR mkkey otherkey.txt || exit 1
expect_fail "mkkey must not overwrite" "already exists" $BOAR mkkey key.txt
[ "$(stat -c %a key.txt 2>/dev/null || stat -f %Lp key.txt)" = 600 ] || { echo "Key file has wrong permissions" >&2; exit 1; }
echo "not a key" >badkey.txt
expect_fail "serve with bad key file" "Not a valid boar key file" $BOAR serve -p10002 --keyfile badkey.txt "$REPO"

expect_fail "key, but server has none" "not configured for encrypted connections" env BOAR_KEYFILE=key.txt $BOAR --repo=$URL sessions
expect_ok "key, server has none, insecure allowed by client" env BOAR_KEYFILE=key.txt BOAR_ALLOW_INSECURE=1 $BOAR --repo=$URL sessions
grep -q "INSECURE" client.log || { echo "Missing client warning" >&2; exit 1; }
stop_server

#
# Server with a key (the normal case)
#
PORT=10003
URL=boar://127.0.0.1:${PORT}
start_server $PORT --keyfile key.txt
expect_ok "right key" env BOAR_KEYFILE=key.txt $BOAR --repo=$URL sessions
grep -q "INSECURE" client.log && { echo "Unexpected client warning" >&2; exit 1; }
expect_ok "right key, insecure allowed by client" env BOAR_KEYFILE=key.txt BOAR_ALLOW_INSECURE=1 $BOAR --repo=$URL sessions
grep -q "INSECURE" client.log && { echo "Client downgraded needlessly" >&2; exit 1; }
expect_fail "wrong key" "Authentication failed" env BOAR_KEYFILE=otherkey.txt $BOAR --repo=$URL sessions
expect_fail "wrong key, insecure allowed by client" "Authentication failed" env BOAR_KEYFILE=otherkey.txt BOAR_ALLOW_INSECURE=1 $BOAR --repo=$URL sessions
expect_fail "bad key file" "Not a valid boar key file" env BOAR_KEYFILE=badkey.txt $BOAR --repo=$URL sessions
expect_fail "no key" "requires its key" $BOAR --repo=$URL sessions
expect_fail "insecure client" "does not accept insecure connections" env BOAR_ALLOW_INSECURE=1 $BOAR --repo=$URL sessions
expect_fail "legacy client" "incompatible version" $PYTHON_BINARY legacy_client.py $PORT

# Round trip some real data, large enough to span many encrypted records
mkdir tree || exit 1
head -c 3000000 /dev/urandom >tree/random.bin
echo "small" >tree/small.txt
export BOAR_KEYFILE=key.txt
$BOAR --repo=$URL import -q tree TestSession >import.log 2>&1 || { cat import.log server.log; echo "Import failed" >&2; exit 1; }
$BOAR --repo=$URL co TestSession co >co.log 2>&1 || { cat co.log server.log; echo "Checkout failed" >&2; exit 1; }
diff -r tree co || { echo "Checked out tree differs" >&2; exit 1; }
$BOAR --repo=$URL verify >verify.log 2>&1 || { cat verify.log; echo "Verify failed" >&2; exit 1; }
unset BOAR_KEYFILE
# The random data must not be visible on the wire: covered by tests/test_securestream.py
stop_server

#
# Server with a key that also accepts insecure clients (transition mode)
#
PORT=10004
URL=boar://127.0.0.1:${PORT}
start_server $PORT --keyfile key.txt --allow-insecure
grep -q "WARNING: This server accepts insecure connections" server.log || { echo "Missing server warning" >&2; exit 1; }
expect_ok "right key, transition server" env BOAR_KEYFILE=key.txt $BOAR --repo=$URL sessions
grep -q "INSECURE" client.log && { echo "Unexpected client warning" >&2; exit 1; }
expect_fail "wrong key, transition server" "Authentication failed" env BOAR_KEYFILE=otherkey.txt $BOAR --repo=$URL sessions
expect_ok "insecure client, transition server" env BOAR_ALLOW_INSECURE=1 $BOAR --repo=$URL sessions
expect_ok "legacy client, transition server" $PYTHON_BINARY legacy_client.py $PORT
stop_server

true
