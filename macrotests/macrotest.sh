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

#export PATH="$PATH:$TESTDIR/../"
unset REPO_PATH
export BOAR="$TESTDIR/../boar"
export BOARMOUNT="$TESTDIR/../boarmount"

echo "Starting"

chmod -R a+w $CLONE 2>/dev/null
rm -r $REPO test_tree $CLONE 2>/dev/null

export BOARTESTHOME=`pwd`

testcases=test_*.sh

if [ "$1" != "" ]; then
    testcases="$@"
fi

for testcase in $testcases; do
    echo "--- Executing $testcase"
    TMPDIR=`mktemp --tmpdir=/tmp -d "boar-${testcase}.XXXXXX"`
    ( cd $TMPDIR && bash $BOARTESTHOME/${testcase} ) || { echo "*** Test case $testcase failed ($TMPDIR)"; exit 1; }
    rm -r $TMPDIR || { echo "Couldn't clean up after test"; exit 1; }
done

echo "All tests completed ok"
