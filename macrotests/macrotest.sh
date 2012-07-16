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

export PATH="$BOARTESTHOME:$PATH"

testcases=test_*.sh

if [ "$1" != "" ]; then
    testcases="$@"
fi

for testcase in $testcases; do
    echo -n "Executing $testcase..."
    TMPDIR=`mktemp --tmpdir=/tmp -d "boar-${testcase}.XXXXXX"`
    OUTPUT="${TMPDIR}.log"
    export BOAR_CACHEDIR="$TMPDIR/cache"
    ( cd $TMPDIR && bash $BOARTESTHOME/${testcase} >$OUTPUT 2>&1 ) ||
	{
	    echo
	    cat $OUTPUT
	    echo "*** Test case $testcase failed ($TMPDIR)"
	    echo "*** Output in $OUTPUT"
	    exit 1
        }
    rm -r $TMPDIR || { echo "Couldn't clean up after test"; exit 1; }
    rm $OUTPUT || { echo "Couldn't clean up after test"; exit 1; }
    echo " OK"
done

echo "All tests completed ok"
