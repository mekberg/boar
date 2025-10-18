#!/bin/bash

export BOAR_CACHEDIR=`mktemp --tmpdir=/tmp/ -d "boar_tests_cache_XXXXX"`
export BOAR_SERVER_CLI="`pwd`/boar"

# Prefer Python from active virtual environment
if [ -n "$VIRTUAL_ENV" ]; then
    if [ -x "$VIRTUAL_ENV/bin/python" ]; then
        export PYTHON_BINARY="$VIRTUAL_ENV/bin/python"
    elif [ -x "$VIRTUAL_ENV/bin/python3" ]; then
        export PYTHON_BINARY="$VIRTUAL_ENV/bin/python3"
    fi
    export PATH="$VIRTUAL_ENV/bin:$PATH"
fi

if [ -z "$PYTHON_BINARY" ]; then
    export PYTHON_BINARY=$(head -n1 $BOAR_SERVER_CLI|cut -d ' ' -f2)
fi
#
# Test without deduplication
#
if ! command -v "$PYTHON_BINARY" >/dev/null 2>&1; then
    if command -v python3 >/dev/null 2>&1; then
        PYTHON_BINARY=$(command -v python3)
    elif command -v python >/dev/null 2>&1; then
        PYTHON_BINARY=$(command -v python)
    else
        echo "ERROR: No suitable Python interpreter found (looked for $PYTHON_BINARY, python3, python)"
        exit 1
    fi
fi

test -e run_tests.sh || { echo "This command must be executed in the boar installation top dir"; exit 1; }
"$PYTHON_BINARY" - <<'PY'
import importlib.util
import sys

if importlib.util.find_spec("cdedup") is not None:
    print("ERROR: dedup module must not be installed for these tests", file=sys.stderr)
    raise SystemExit(1)
PY

#
# Test WITHOUT deduplication
#

for unittest in tests/test_*.py blobrepo/tests/test_*.py; do
    echo "Excuting $unittest (cachedir $BOAR_CACHEDIR)"
    BOAR_SKIP_DEDUP_TESTS=1 $PYTHON_BINARY $unittest || { echo "Unittest $unittest failed"; exit 1; }
done

rm -r $BOAR_CACHEDIR

echo "Executing local macro tests without deduplication"
BOAR_SKIP_DEDUP_TESTS=1 BOAR_TEST_REMOTE_REPO=0 macrotests/macrotest.sh || { echo "Macrotests (local) failed"; exit 1; }
