#!/bin/bash

# Copyright 2010 Mats Ekberg
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

TESTDIR=~+/`dirname $0`
cd $TESTDIR

unset REPO_PATH # Don't harm any innocent repos

#export COVERAGE_FILE="$TESTDIR/boar.coverage"
#export BOAR="coverage run -a $TESTDIR/../boar"
export BOAR="$TESTDIR/../boar"
export BOARMOUNT="$TESTDIR/../boarmount"
export BOARTESTHOME=`pwd`
export BOAR_SERVER_CLI="$BOARTESTHOME/../boar"

# Prefer Python from active virtual environment
if [ -n "$VIRTUAL_ENV" ] && [ -x "$VIRTUAL_ENV/bin/python" ]; then
    export PYTHON_BINARY="$VIRTUAL_ENV/bin/python"
    export PATH="$VIRTUAL_ENV/bin:$PATH"
else
    export PYTHON_BINARY=$(head -n1 $BOAR_SERVER_CLI|cut -d ' ' -f2)
fi

export PATH="$BOARTESTHOME:$PATH"

testcases=test_*.sh

if [ "$1" != "" ]; then
    testcases="$@"
fi

# By default, run quietly: only show output on failure. Set VERBOSE=1 to see progress.
for testcase in $testcases; do
    [ -n "$VERBOSE" ] && echo "Running $testcase"
    TMPDIR=`mktemp --tmpdir=/tmp -d "boar-${testcase}.XXXXXX"`
    OUTPUT="${TMPDIR}.log"
    export BOAR_CACHEDIR="$TMPDIR/cache"
    export BOAR_HIDE_PROGRESS=1
    # Execute the test in an isolated temp dir, capturing all output to the log
    ( cd "$TMPDIR" && bash "$BOARTESTHOME/${testcase}" ) >"$OUTPUT" 2>&1 || {
        # On failure, print the captured output and keep the temp dir for inspection
        [ -z "$VERBOSE" ] && echo "Failure in $testcase"
        cat "$OUTPUT"
        echo "*** Test case $testcase failed ($TMPDIR)"
        echo "*** Output in $OUTPUT"
        exit 1
    }
    # Clean up only on success
    rm -r "$TMPDIR" || { echo "Couldn't clean up after test"; exit 1; }
    rm -f "$OUTPUT" || { echo "Couldn't clean up after test"; exit 1; }
done

[ -n "$VERBOSE" ] && echo "All macrotests completed ok"
