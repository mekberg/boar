#!/bin/bash

export BOAR_CACHEDIR=`mktemp --tmpdir=/tmp/ -d "boar_tests_cache_XXXXX"`
export BOAR_SERVER_CLI="`pwd`/boar"
export PYTHON_BINARY=$(head -n1 $BOAR_SERVER_CLI|cut -d ' ' -f2)

test -e run_tests.sh || { echo "This command must be executed in the boar installation top dir"; exit 1; }
test ! -e cdedup.so || { echo "ERROR: dedup module must not be installed for these tests"; exit 1; }

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
