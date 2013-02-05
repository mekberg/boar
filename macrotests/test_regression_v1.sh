# Test for regression issues with repo and workdir format from
# repository format version v1.

testdir="`pwd`"
tar xzf $BOARTESTHOME/regression-v1.tar.gz || exit 1
REPO=$testdir/regression-v1/TESTREPO
cd regression-v1/workdir

# Relocate the workdir pointer to the repo.  Also, since the test data
# contains a half-finished commit, let's change the session_id to
# point at the latest revision (the one in progress of being
# committed). This should probably be done with some future boar
# commands eventually.
cat >$testdir/regression-v1/workdir/.boar/info <<EOF || exit 1
{
    "session_name": "Test",
    "offset": "",
    "session_id": 7,
    "repo_path": "$REPO"
}
EOF

REPO_PATH=$REPO $BOAR status -q |tee $testdir/status.txt || { echo "Couldn't execute status (note: output redirected)"; exit 1; }
if [ `grep -c . $testdir/status.txt` -ne 1 ]; then 
    cat $testdir/status.txt
    echo "Did not expect status to show any changes"; exit 1; 
fi
md5sum -c ../r7.md5 || { echo "r7.md5 failed"; exit 1; }
REPO_PATH=$REPO $BOAR update -r2 || { echo "Couldn't execute update"; exit 1; }
md5sum -c ../r2.md5 || { echo "r2.md5 failed"; exit 1; }
REPO_PATH=$REPO $BOAR update -r6 || { echo "Couldn't execute status"; exit 1; }
md5sum -c ../r6.md5 || { echo "r6.md5 failed"; exit 1; }
cp some_text.txt some_text2.txt
REPO_PATH=$REPO $BOAR ci && { echo "Ci executed ok even though workdir is out of date"; exit 1; }
REPO_PATH=$REPO $BOAR update || { echo "Couldn't execute update to latest version"; exit 1; }
REPO_PATH=$REPO $BOAR ci || { echo "Couldn't execute ci"; exit 1; }
REPO_PATH=$REPO $BOAR verify || { echo "Couldn't verify"; exit 1; }

# Test disabled - recipes dir has been ressurrected in v5
#test ! -e $REPO/recipes || { echo "recipes dir wasn't deleted"; exit 1; }

cd $testdir || exit 1
rm -r regression-v1 || exit 1

echo "--- Test future version detection"
tar xzf $BOARTESTHOME/regression-v1.tar.gz || exit 1
echo "6" >$REPO/version.txt || exit 1
REPO_PATH=$REPO $BOAR verify && { echo "Future version repo should fail"; exit 1; }
(REPO_PATH=$REPO $BOAR verify 2>&1 | grep "Repo is from a future boar version.") || \
    { echo "Operation didn't give expected error message"; exit 1; }
rm -r regression-v1 || exit 1

echo "--- Test write protected repo"
# Boar does not yet handle write-protected repos with pending
# changes. Make sure that such repos are detected and handled
# gracefully.
tar xzf $BOARTESTHOME/regression-v1.tar.gz || exit 1
test -e $REPO/queue/7 || { echo "Tested repo must contain an uncompleted commit"; exit 1; }
chmod -R a-w $REPO || exit 1
REPO_PATH=$REPO $BOAR verify && { echo "Operation expected to fail due to write protect and pending changes."; exit 1; }
(REPO_PATH=$REPO $BOAR verify 2>&1 | grep "Repo is write protected with pending changes. Cannot continue.") || \
    { echo "Operation didn't give expected error message"; exit 1; }
chmod -R u+w $REPO || exit 1
rm -r regression-v1 || exit 1

echo "--- Test repo cloning"
tar xzf $BOARTESTHOME/regression-v1.tar.gz || exit 1
$BOAR clone $REPO clone || { echo "Couldn't clone"; exit 1; }
rm -r regression-v1 || exit 1

echo "--- Test cat"
tar xzf $BOARTESTHOME/regression-v1.tar.gz || exit 1
($BOAR cat --repo=$REPO Test/some_text.txt | md5sum - | grep 1aa9fa286a98d0bb37bc0164c23de704) || {
    echo "Unexpected cat output"; exit 1; } 
rm -r regression-v1 || exit 1
tar xzf $BOARTESTHOME/regression-v1.tar.gz || exit 1
($BOAR cat --repo=$REPO -B 1aa9fa286a98d0bb37bc0164c23de704 | md5sum - | grep 1aa9fa286a98d0bb37bc0164c23de704) || { 
    echo "Unexpected cat -B output"; exit 1; } 

echo "--- Excercise repo"
$BOARTESTHOME/excercise_repo.sh "$BOAR" $REPO || { echo "Excercise of v1 repo failed"; exit 1; }