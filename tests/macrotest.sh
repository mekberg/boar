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

# Test check-in
(cd test_tree && $CMD ci) || { echo "Couldn't check in tree"; exit 1; }
rm -r test_tree || { echo "Couldn't remove test tree after check-in"; exit 1; }
REPO_PATH=$REPO $CMD co MyTestSession test_tree || { echo "Couldn't check out tree"; exit 1; }
md5sum -c test_tree.md5 || { echo "Test tree failed md5 after check-out"; exit 1; }


rm -r $REPO test_tree
echo "All tests completed ok!"



