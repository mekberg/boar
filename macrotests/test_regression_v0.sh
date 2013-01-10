# Test for regression issues with repo and workdir format from
# boar-daily.11-Jul-2011 (repository format version v0).

testdir="`pwd`"
tar xzf $BOARTESTHOME/regression-boar-daily.11-Jul-2011.tar.gz || exit 1
REPO=$testdir/regression-boar-daily.11-Jul-2011/TESTREPO
NOPENDINGREPO=$testdir/regression-boar-daily.11-Jul-2011/TESTREPO-nopending # identical, but no pending changes
cd regression-boar-daily.11-Jul-2011/workdir

# Relocate the workdir pointer to the repo.  Also, since the test data
# contains a half-finished commit, let's change the session_id to
# point at the latest revision (the one in progress of being
# committed).

(cd $testdir/regression-boar-daily.11-Jul-2011/workdir && $BOAR relocate $REPO) || exit 1
(cd $testdir/regression-boar-daily.11-Jul-2011/workdir && $BOAR update --ignore-changes -r 7) || exit 1

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
test ! -e $REPO/recipes || { echo "recipes dir wasn't deleted"; exit 1; }
cd $testdir || exit 1
rm -r regression-boar-daily.11-Jul-2011 || exit 1

echo "--- Test explicit version 0 repository"
# version 0 repos does not normally have a version.txt
tar xzf $BOARTESTHOME/regression-boar-daily.11-Jul-2011.tar.gz || exit 1
echo "0" >$REPO/version.txt || exit 1
REPO_PATH=$REPO $BOAR verify || { echo "Couldn't verify"; exit 1; }
rm -r regression-boar-daily.11-Jul-2011 || exit 1

echo "--- Test future version detection"
tar xzf $BOARTESTHOME/regression-boar-daily.11-Jul-2011.tar.gz || exit 1
echo "6" >$REPO/version.txt || exit 1
REPO_PATH=$REPO $BOAR verify && { echo "Future version repo should fail"; exit 1; }
(REPO_PATH=$REPO $BOAR verify 2>&1 | grep "Repo is from a future boar version.") || { 
    echo "Operation didn't give expected error message"
    echo "HINT: Did you update repo version? Then you must also update this test!"; 
    exit 1; 
}
rm -r regression-boar-daily.11-Jul-2011 || exit 1

echo "--- Test repository without recovery.txt"
# version 0 repos does normally have a recovery.txt
tar xzf $BOARTESTHOME/regression-boar-daily.11-Jul-2011.tar.gz || exit 1
rm $REPO/recovery.txt || exit 1
REPO_PATH=$REPO $BOAR verify || { echo "Couldn't verify"; exit 1; }
test -e $REPO/recovery.txt || { echo "recovery.txt wasn't recreated"; exit 1; }
rm -r regression-boar-daily.11-Jul-2011 || exit 1

echo "--- Test repository without recipes dir"
# version 0 repos may or may not have a recipes dir
tar xzf $BOARTESTHOME/regression-boar-daily.11-Jul-2011.tar.gz || exit 1
rmdir $REPO/recipes || exit 1
REPO_PATH=$REPO $BOAR verify || { echo "Couldn't verify"; exit 1; }
rm -r regression-boar-daily.11-Jul-2011 || exit 1

echo "--- Test write protected repo WITH pending changes"
# Boar does not yet handle write-protected repos with pending
# changes. Make sure that such repos are detected and handled
# gracefully.
tar xzf $BOARTESTHOME/regression-boar-daily.11-Jul-2011.tar.gz || exit 1
test -e $REPO/queue/7 || { echo "Tested repo must contain an uncompleted commit"; exit 1; }
chmod -R a-w $REPO || exit 1
REPO_PATH=$REPO $BOAR verify && { echo "Operation expected to fail due to write protect and pending changes."; exit 1; }
(REPO_PATH=$REPO $BOAR verify 2>&1 | grep "Repo is write protected with pending changes. Cannot continue.") || \
    { echo "Operation didn't give expected error message"; exit 1; }
chmod -R u+w $REPO || exit 1
rm -r regression-boar-daily.11-Jul-2011 || exit 1

echo "--- Test write protected repo WITHOUT pending changes"
# Write protected repos should be accessible read-only
tar xzf $BOARTESTHOME/regression-boar-daily.11-Jul-2011.tar.gz || exit 1
rm -r $REPO || exit # Just so that we'll notice if we mix things up with NOPENDINGREPO
test -e $NOPENDINGREPO/queue/7 && { echo "Tested repo must NOT contain an uncompleted commit"; exit 1; }
test -e $NOPENDINGREPO/version.txt && { echo "Tested repo must be version 0"; exit 1; }
chmod -R a-w $NOPENDINGREPO || exit 1
REPO_PATH=$NOPENDINGREPO $BOAR ls || { echo "ls operation should succeed on read-only repo."; exit 1; }
REPO_PATH=$NOPENDINGREPO $BOAR verify || { echo "Verify operation should succeed on read-only repo."; exit 1; }
REPO_PATH=$NOPENDINGREPO $BOAR setprop MySession ignore "*.tmp" && { echo "Setprop operation should fail on read-only repo."; exit 1; }
chmod -R u+w $NOPENDINGREPO || exit 1
rm -r regression-boar-daily.11-Jul-2011 || exit 1

echo "--- Test simple aborted repo upgrade"
# Simulate a partially-upgraded v0 repo by removing the version.txt
# after upgrade and make sure the repo upgrade is resumed successfully
tar xzf $BOARTESTHOME/regression-boar-daily.11-Jul-2011.tar.gz || exit 1
REPO_PATH=$REPO $BOAR verify || { echo "Upgrade failed"; exit 1; }
rm regression-boar-daily.11-Jul-2011/TESTREPO/version.txt || exit 1
REPO_PATH=$REPO $BOAR verify || { echo "Upgrade resumption failed"; exit 1; }
rm -r regression-boar-daily.11-Jul-2011 || exit 1

echo "--- Test repo cloning"
tar xzf $BOARTESTHOME/regression-boar-daily.11-Jul-2011.tar.gz || exit 1
$BOAR clone $REPO clone || { echo "Couldn't clone"; exit 1; }
rm -r regression-boar-daily.11-Jul-2011 || exit 1

echo "--- Test legal missing snapshot"
# Test the case that the user has manually removed a non-base
# snapshot. This should be legal.
tar xzf $BOARTESTHOME/regression-boar-daily.11-Jul-2011.tar.gz || exit 1
rm -r $REPO/sessions/4 || exit 1
$BOARTESTHOME/excercise_repo.sh "$BOAR" $REPO || { echo "Excercise of repo with legal missing snapshots failed"; exit 1; }
