#!/bin/bash
TESTDIR=~+/`dirname $0`
cd $TESTDIR

export PATH="$PATH:$TESTDIR/../"
CMD="cmd.py"
REPO="$TESTDIR/TESTREPO"

rm -r $REPO test_tree 2>/dev/null

tar -xvzf test_tree.tar.gz || { echo "Couldn't create test tree"; exit 1; }
md5sum -c test_tree.md5 || { echo "Test tree failed md5 before check-in"; exit 1; }
$CMD mkrepo $REPO || { echo "Couldn't create repo"; exit 1; }
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
#find test_tree -type f -a ! -ipath *.meta*` || { echo "More files than expected in checkout"; exit 1; }



rm -r $REPO test_tree
echo "All tests completed ok!"

