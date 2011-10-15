# Test for regression issues with repo and workdir format from
# boar-daily.11-Jul-2011 (repository format version v0).

TESTHOME=~+/`dirname $0`
BOAR=$TESTHOME/../boar
testdir="/tmp/repo-regression$$"
mkdir $testdir || exit 1
cd $testdir || exit 1
tar xzf $TESTHOME/regression-boar-daily.11-Jul-2011.tar.gz || exit 1
REPO=$testdir/regression-boar-daily.11-Jul-2011/TESTREPO
cd regression-boar-daily.11-Jul-2011/workdir

# Relocate the workdir pointer to the repo.  Also, since the test data
# contains a half-finished commit, let's change the session_id to
# point at the latest revision (the one in progress of being
# committed). This should probably be done with some future boar
# commands eventually.
cat >$testdir/regression-boar-daily.11-Jul-2011/workdir/.meta/info <<EOF || exit 1
{
    "session_name": "Test",
    "offset": "",
    "session_id": 7,
    "repo_path": "$REPO"
}
EOF

REPO_PATH=$REPO $BOAR status >$testdir/status.txt || { echo "Couldn't execute status"; exit 1; }
if [ `grep -c . $testdir/status.txt` -ne 1 ]; then 
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
tar xzf $TESTHOME/regression-boar-daily.11-Jul-2011.tar.gz || exit 1
echo "0" >$REPO/version.txt || exit 1
REPO_PATH=$REPO $BOAR verify || { echo "Couldn't verify"; exit 1; }
rm -r regression-boar-daily.11-Jul-2011 || exit 1

echo "--- Test future version detection"
tar xzf $TESTHOME/regression-boar-daily.11-Jul-2011.tar.gz || exit 1
echo "2" >$REPO/version.txt || exit 1
REPO_PATH=$REPO $BOAR verify && { echo "Future version repo should fail"; exit 1; }
rm -r regression-boar-daily.11-Jul-2011 || exit 1

echo "--- Test repository without recovery.txt"
# version 0 repos does normally have a recovery.txt
tar xzf $TESTHOME/regression-boar-daily.11-Jul-2011.tar.gz || exit 1
rm $REPO/recovery.txt || exit 1
REPO_PATH=$REPO $BOAR verify || { echo "Couldn't verify"; exit 1; }
test -e $REPO/recovery.txt || { echo "recovery.txt wasn't recreated"; exit 1; }
rm -r regression-boar-daily.11-Jul-2011 || exit 1

echo "--- Test repository without recipes dir"
# version 0 repos may or may not have a recipes dir
tar xzf $TESTHOME/regression-boar-daily.11-Jul-2011.tar.gz || exit 1
rmdir $REPO/recipes || exit 1
REPO_PATH=$REPO $BOAR verify || { echo "Couldn't verify"; exit 1; }
rm -r regression-boar-daily.11-Jul-2011 || exit 1

echo "--- Test repo cloning"
tar xzf $TESTHOME/regression-boar-daily.11-Jul-2011.tar.gz || exit 1
$BOAR clone $REPO clone || { echo "Couldn't clone"; exit 1; }

rm -r $testdir
