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

export PATH="$PATH:$TESTDIR/../"
CMD="boar"
REPO="$TESTDIR/TESTREPO"
CLONE="${REPO}_CLONE"

rm -r $REPO test_tree $CLONE 2>/dev/null

tar -xvzf test_tree.tar.gz || { echo "Couldn't create test tree"; exit 1; }
md5sum -c test_tree.md5 || { echo "Test tree failed md5 before check-in"; exit 1; }
$CMD mkrepo $REPO || { echo "Couldn't create repo"; exit 1; }
REPO_PATH=$REPO $CMD mksession MyTestSession || { echo "Couldn't create session"; exit 1; }
REPO_PATH=$REPO $CMD import test_tree MyTestSession || { echo "Couldn't import tree"; exit 1; }
rm -r test_tree || { echo "Couldn't remove test tree after import"; exit 1; }
REPO_PATH=$REPO $CMD co MyTestSession test_tree || { echo "Couldn't check out tree"; exit 1; }
md5sum -c test_tree.md5 || { echo "Test tree failed md5 after check-out"; exit 1; }

echo Test unchanged check-in
(cd test_tree && $CMD ci) || { echo "Couldn't check in tree"; exit 1; }
rm -r test_tree || { echo "Couldn't remove test tree after check-in"; exit 1; }
REPO_PATH=$REPO $CMD co MyTestSession test_tree || { echo "Couldn't check out tree"; exit 1; }
md5sum -c test_tree.md5 || { echo "Test tree failed md5 after unmodified check-in"; exit 1; }

echo Test adding files to a base session
rm -r test_tree || { echo "Couldn't remove test tree"; exit 1; }
tar -xvzf test_tree_addition.tar.gz || { echo "Couldn't create test tree for addition"; exit 1; }
REPO_PATH=$REPO $CMD import test_tree MyTestSession || { echo "Couldn't import added files"; exit 1; }
rm -r test_tree || { echo "Couldn't remove test tree"; exit 1; }
REPO_PATH=$REPO $CMD co MyTestSession test_tree || { echo "Couldn't check out tree"; exit 1; }
md5sum -c test_tree.md5 || { echo "Test tree failed md5 after addition"; exit 1; }
md5sum -c test_tree_addition.md5 || { echo "Test tree addition failed md5 after addition"; exit 1; }

echo Test adding the same file again
rm -r test_tree || { echo "Couldn't remove test tree"; exit 1; }
tar -xvzf test_tree_addition.tar.gz || { echo "Couldn't create test tree for addition"; exit 1; }
REPO_PATH=$REPO $CMD import test_tree MyTestSession || { echo "Couldn't import added files"; exit 1; }
rm -r test_tree || { echo "Couldn't remove test tree"; exit 1; }
REPO_PATH=$REPO $CMD co MyTestSession test_tree || { echo "Couldn't check out tree"; exit 1; }
md5sum -c test_tree.md5 || { echo "Test tree failed md5 after addition"; exit 1; }
md5sum -c test_tree_addition.md5 || { echo "Test tree addition failed md5 after addition"; exit 1; }

echo Test offset checkout
rm -r test_tree || { echo "Couldn't remove test tree"; exit 1; }
REPO_PATH=$REPO $CMD co MyTestSession/subdir test_tree || { echo "Couldn't check out tree"; exit 1; }
md5sum -c <<EOF || { echo "Offset checkout failed"; exit 1; }
2490f86515a5a58067c2a1ca3e239299  test_tree/fil1.txt
EOF
test `find test_tree -type f -a ! -ipath *.meta*` == "test_tree/fil1.txt" || { echo "More files than expected in checkout"; exit 1; }

echo Test offset checkin
echo "Some content" >test_tree/nysubfil.txt
(cd test_tree && $CMD ci) || { echo "Couldn't check in tree"; exit 1; }
rm -r test_tree || { echo "Couldn't remove test tree"; exit 1; }
REPO_PATH=$REPO $CMD co MyTestSession/subdir test_tree || { echo "Couldn't check out tree"; exit 1; }
md5sum -c <<EOF || { echo "Offset checkout failed"; exit 1; }
2490f86515a5a58067c2a1ca3e239299  test_tree/fil1.txt
581ab2d89f05c294d4fe69c623bdef83  test_tree/nysubfil.txt
EOF

echo Test offset import / add file / status
rm -r test_tree || { echo "Couldn't remove test tree"; exit 1; }
mkdir test_tree || { echo "Couldn't create test_tree dir"; exit 1; }
REPO_PATH=$REPO $CMD import -w test_tree MyTestSession/new_import || { echo "Couldn't import dir"; exit 1; }
(cd test_tree && $CMD status) || { echo "Status command 1 failed"; exit 1; }
echo "Some new content" >test_tree/new_file.txt
(cd test_tree && $CMD status) || { echo "Status command 2 failed"; exit 1; }
#find test_tree -type f -a ! -ipath *.meta*` || { echo "More files than expected in checkout"; exit 1; }

echo Test repo cloning
$CMD clone $REPO $CLONE || { echo "Couldn't clone repo"; exit 1; }
$CMD diffrepo $REPO $CLONE || { echo "Some differences where found in cloned repo"; exit 1; }
rm -r $CLONE || { echo "Couldn't remove cloned repo"; exit 1; }

echo Test recipe checkout
rm -r test_tree || { echo "Couldn't remove test tree"; exit 1; }
tar -xzf reciperepo.tar.gz
REPO_PATH=`pwd`/reciperepo $CMD verify || { echo "Recipe repo failed verify"; exit 1; }
REPO_PATH=`pwd`/reciperepo $CMD co Alice test_tree || { echo "Couldn't check out tree"; exit 1; }
(cd test_tree && $CMD status -v) || { echo "Status command failed"; exit 1; }
md5sum -c <<EOF || { echo "Recipe checkout failed"; exit 1; }
9b97d0a697dc503fb4c53ea01bd23dc7  test_tree/alice.txt
EOF
rm -r reciperepo || { echo "Couldn't remove recipe repo"; exit 1; }

rm -r $REPO test_tree
echo "All tests completed ok!"

