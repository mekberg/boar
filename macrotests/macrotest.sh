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
BOAR="$TESTDIR/../boar"
BOARMOUNT="$TESTDIR/../boarmount"
REPO="$TESTDIR/TESTREPO"
CLONE="${REPO}_CLONE"

rm -r $REPO test_tree $CLONE 2>/dev/null

echo --- Test basic command line behaviour

($BOAR | grep "Boar commands:" >/dev/null ) || { echo "No subcommand did not yield help"; exit 1; }
($BOAR --help | grep "Boar commands:" >/dev/null ) || { echo "No subcommand did not yield help"; exit 1; }
$BOAR >/dev/null && { echo "No subcommand should cause an exit error code"; exit 1; }
$BOAR nonexisting_cmd >/dev/null && { echo "Non-existing subcommand should cause an exit error code"; exit 1; }

echo --- Test --help flag
for subcmd in ci clone co diffrepo info import list locate mkrepo mksession status update verify; do
    echo Testing $subcmd --help
    ( REPO_PATH="" $BOAR $subcmd --help | grep "Usage:" >/dev/null ) || \
	{ echo "Subcommand '$subcmd' did not give a help message with --help flag"; exit 1; }
done

tar -xvzf test_tree.tar.gz || { echo "Couldn't create test tree"; exit 1; }
md5sum -c test_tree.md5 || { echo "Test tree failed md5 before check-in"; exit 1; }
$BOAR mkrepo $REPO || { echo "Couldn't create repo"; exit 1; }
REPO_PATH=$REPO $BOAR mksession MyTestSession || { echo "Couldn't create session"; exit 1; }
REPO_PATH=$REPO $BOAR import -v test_tree MyTestSession || { echo "Couldn't import tree"; exit 1; }
rm -r test_tree || { echo "Couldn't remove test tree after import"; exit 1; }
REPO_PATH=$REPO $BOAR co MyTestSession test_tree || { echo "Couldn't check out tree"; exit 1; }
md5sum -c test_tree.md5 || { echo "Test tree failed md5 after check-out"; exit 1; }

echo --- Test unchanged check-in
(cd test_tree && $BOAR ci) || { echo "Couldn't check in tree"; exit 1; }
rm -r test_tree || { echo "Couldn't remove test tree after check-in"; exit 1; }
REPO_PATH=$REPO $BOAR co MyTestSession test_tree || { echo "Couldn't check out tree"; exit 1; }
md5sum -c test_tree.md5 || { echo "Test tree failed md5 after unmodified check-in"; exit 1; }

echo --- Test status command
( cd test_tree && $BOAR status -v ) || { echo "Couldn't execute status command"; exit 1; }
# By redirecting, we are forcing the output stream to ascii, which will blow up on unicode.
( cd test_tree && $BOAR status -v >/dev/null ) || { echo "Couldn't execute redirected status command"; exit 1; }

echo --- Test info command
( cd test_tree && $BOAR info ) || { echo "Couldn't execute info command"; exit 1; }
( cd test_tree && $BOAR info | grep "Workdir root" >/dev/null ) || { echo "Info command didn't return expected data"; exit 1; }

echo --- Test exportmd5 command
( cd test_tree && $BOAR exportmd5 ) || { echo "Couldn't export md5sum"; exit 1; }
( cd test_tree && md5sum -c md5sum.txt ) || { echo "Couldn't verify exported md5sum"; exit 1; }
( cd test_tree && rm md5sum.txt ) || { echo "Couldn't remove exported md5sum"; exit 1; }

echo --- Test adding files to a base session
rm -r test_tree || { echo "Couldn't remove test tree"; exit 1; }
tar -xvzf test_tree_addition.tar.gz || { echo "Couldn't create test tree for addition"; exit 1; }
REPO_PATH=$REPO $BOAR import -v test_tree MyTestSession || { echo "Couldn't import added files"; exit 1; }
rm -r test_tree || { echo "Couldn't remove test tree"; exit 1; }
REPO_PATH=$REPO $BOAR co MyTestSession test_tree || { echo "Couldn't check out tree"; exit 1; }
md5sum -c test_tree.md5 || { echo "Test tree failed md5 after addition"; exit 1; }
md5sum -c test_tree_addition.md5 || { echo "Test tree addition failed md5 after addition"; exit 1; }

echo --- Test adding the same file again
rm -r test_tree || { echo "Couldn't remove test tree"; exit 1; }
tar -xvzf test_tree_addition.tar.gz || { echo "Couldn't create test tree for addition"; exit 1; }
REPO_PATH=$REPO $BOAR import -v test_tree MyTestSession || { echo "Couldn't import added files"; exit 1; }
rm -r test_tree || { echo "Couldn't remove test tree"; exit 1; }
REPO_PATH=$REPO $BOAR co MyTestSession test_tree || { echo "Couldn't check out tree"; exit 1; }
md5sum -c test_tree.md5 || { echo "Test tree failed md5 after addition"; exit 1; }
md5sum -c test_tree_addition.md5 || { echo "Test tree addition failed md5 after addition"; exit 1; }

echo --- Test offset checkout
rm -r test_tree || { echo "Couldn't remove test tree"; exit 1; }
REPO_PATH=$REPO $BOAR co MyTestSession/subdir test_tree || { echo "Couldn't check out tree"; exit 1; }
md5sum -c <<EOF || { echo "Offset checkout failed"; exit 1; }
2490f86515a5a58067c2a1ca3e239299  test_tree/fil1.txt
EOF
test `find test_tree -type f -a ! -ipath *.meta*` == "test_tree/fil1.txt" || { echo "More files than expected in checkout"; exit 1; }

echo --- Test offset checkin
echo "Some content" >test_tree/nysubfil.txt
(cd test_tree && $BOAR ci) || { echo "Couldn't check in tree"; exit 1; }
rm -r test_tree || { echo "Couldn't remove test tree"; exit 1; }
REPO_PATH=$REPO $BOAR co MyTestSession/subdir test_tree || { echo "Couldn't check out tree"; exit 1; }
md5sum -c <<EOF || { echo "Offset checkout failed"; exit 1; }
2490f86515a5a58067c2a1ca3e239299  test_tree/fil1.txt
581ab2d89f05c294d4fe69c623bdef83  test_tree/nysubfil.txt
EOF

echo --- Test offset import / add file / status
rm -r test_tree || { echo "Couldn't remove test tree"; exit 1; }
mkdir test_tree || { echo "Couldn't create test_tree dir"; exit 1; }
REPO_PATH=$REPO $BOAR import -v -w test_tree MyTestSession/new_import || { echo "Couldn't import dir"; exit 1; }
(cd test_tree && $BOAR status) || { echo "Status command 1 failed"; exit 1; }
echo "Some new content" >test_tree/new_file.txt
(cd test_tree && $BOAR status) || { echo "Status command 2 failed"; exit 1; }
#find test_tree -type f -a ! -ipath *.meta*` || { echo "More files than expected in checkout"; exit 1; }

echo --- Test verify
REPO_PATH=$REPO $BOAR verify || { echo "Couldn't verify repo"; exit 1; }

echo --- Test repo cloning
$BOAR clone $REPO $CLONE || { echo "Couldn't clone repo"; exit 1; }
$BOAR diffrepo $REPO $CLONE || { echo "Some differences where found in cloned repo"; exit 1; }
rm -r $CLONE || { echo "Couldn't remove cloned repo"; exit 1; }

echo --- Test repo cloning with duplicate files in a new session
rm -r test_tree || { echo "Couldn't remove test tree"; exit 1; }
mkdir test_tree || { echo "Couldn't create test tree"; exit 1; }
echo "Identical Content" >test_tree/file1.txt || { echo "Couldn't create file1.txt"; exit 1; }
echo "Identical Content" >test_tree/file2.txt || { echo "Couldn't create file2.txt"; exit 1; }
REPO_PATH=$REPO $BOAR mksession MyCloneTest || { echo "Couldn't create session"; exit 1; }
REPO_PATH=$REPO $BOAR import -v test_tree MyCloneTest || { echo "Couldn't import tree"; exit 1; }
$BOAR clone $REPO $CLONE || { echo "Couldn't clone repo"; exit 1; }
$BOAR diffrepo $REPO $CLONE || { echo "Some differences where found in cloned repo"; exit 1; }
rm -r $CLONE || { echo "Couldn't remove cloned repo"; exit 1; }

echo --- Test boarmount
rm -r test_tree || { echo "Couldn't remove test tree"; exit 1; }
REPO_PATH=$REPO $BOAR mksession BoarMount || { echo "Couldn't create boarmount session"; exit 1; }
REPO_PATH=$REPO $BOAR co BoarMount test_tree || { echo "Couldn't co boarmount session"; exit 1; }
tar -xvzf test_tree.tar.gz || { echo "Couldn't create test tree for boarmount"; exit 1; }
md5sum -c test_tree.md5 || { echo "Test tree was corrupt before checking in"; exit 1; }
(cd test_tree && REPO_PATH=$REPO $BOAR ci) || { echo "Couldn't ci boarmount session"; exit 1; }
rm -r test_tree || { echo "Couldn't remove test tree"; exit 1; }
mkdir test_tree || { echo "Couldn't create test_tree dir for mounting"; exit 1; }
$BOARMOUNT $REPO BoarMount test_tree || { echo "Couldn't mount session"; exit 1; }
(mount -l -t fuse.boarmount | grep ~+/test_tree) || { echo "Mounted session does not seem to really be mounted"; exit 1; }
[ `find test_tree|grep -c .` -eq 9 ] || { echo "Mounted tree does not contain expected number of files"; fusermount -u test_tree; exit 1; }
md5sum -c test_tree.md5 || { echo "Mounted session was corrupt"; fusermount -u test_tree; exit 1; }
fusermount -u test_tree

# echo --- Test recipe checkout
# rm -r test_tree || { echo "Couldn't remove test tree"; exit 1; }
# tar -xzf reciperepo.tar.gz
# REPO_PATH=`pwd`/reciperepo $BOAR verify || { echo "Recipe repo failed verify"; exit 1; }
# REPO_PATH=`pwd`/reciperepo $BOAR co Alice test_tree || { echo "Couldn't check out tree"; exit 1; }
# (cd test_tree && $BOAR status -v) || { echo "Status command failed"; exit 1; }
# md5sum -c <<EOF || { echo "Recipe checkout failed"; exit 1; }
# 9b97d0a697dc503fb4c53ea01bd23dc7  test_tree/alice.txt
# EOF
# rm -r reciperepo || { echo "Couldn't remove recipe repo"; exit 1; }

rm -r $REPO test_tree
echo "All tests completed ok!"

