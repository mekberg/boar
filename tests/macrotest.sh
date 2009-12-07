#!/bin/bash
CMD="python ../cmd.py"
tar -xvzf test_tree.tar.gz || { echo "Couldn't create test tree"; exit 1; }
md5sum -c test_tree.md5 || { echo "Test tree failed md5 before check-in"; exit 1; }
$CMD mkrepo TESTREPO || { echo "Couldn't create repo"; exit 1; }
REPO_PATH=TESTREPO $CMD ci test_tree MyTestSession || { echo "Couldn't check in tree"; exit 1; }
rm -r test_tree || { echo "Couldn't remove test tree after check-in"; exit 1; }
REPO_PATH=TESTREPO $CMD co MyTestSession test_tree || { echo "Couldn't check out tree"; exit 1; }
md5sum -c test_tree.md5 || { echo "Test tree failed md5 after check-out"; exit 1; }
rm -rf TESTREPO
echo "All tests completed ok!"



