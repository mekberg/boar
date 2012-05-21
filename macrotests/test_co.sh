# Test that the co command behaves as expected.

export REPO_PATH=TESTREPO
$BOAR mkrepo $REPO_PATH || exit 1
$BOAR mksession --repo=$REPO_PATH TestSessionCo || exit 1
$BOAR co TestSessionCo || exit 1
test -e TestSessionCo || { echo "Default workdir name should be the session name"; exit 1; }

mkdir TestSessionCo/cosubdir || exit 1
echo "Rev 2" >TestSessionCo/r2.txt || exit 1
(cd TestSessionCo && $BOAR ci -q) || exit 1

rm TestSessionCo/r2.txt || exit 1
echo "Rev 3" >TestSessionCo/r3.txt || exit 1
(cd TestSessionCo && $BOAR ci -q) || exit 1

rm TestSessionCo/r3.txt || exit 1
echo "Rev 4" >TestSessionCo/r4.txt || exit 1
(cd TestSessionCo && $BOAR ci -q) || exit 1

for rev in 2 3 4; do
    # Test -r flag
    $BOAR co -r $rev TestSessionCo "wd_rev${rev}" || exit 1
    test -e "wd_rev${rev}/r${rev}.txt" || { echo "Rev ${rev} missing file"; exit 1; }
    test `ls wd_rev${rev}/*.txt | wc -l` = 1 || { echo "Rev ${rev} contains unexpected file"; exit 1; }
    test "`cat wd_rev${rev}/r${rev}.txt`" = "Rev $rev" || { echo "Rev ${rev} contains unexpected file content"; exit 1; }
done

# Test latest rev (should be rev 4)
$BOAR co TestSessionCo "wd_rev_latest" || exit 1
test -e "wd_rev_latest/r4.txt" || { echo "Latest rev missing file"; exit 1; }
test `ls wd_rev_latest/*.txt | wc -l` = 1 || { echo "Latest rev contains unexpected file"; exit 1; }
test "`cat wd_rev_latest/r4.txt`" = "Rev 4" || { echo "Latest rev contains unexpected file content"; exit 1; }

echo "Subdir file" >TestSessionCo/cosubdir/subdir_file.txt || exit 1
(cd TestSessionCo && $BOAR ci -q) || exit 1

$BOAR co TestSessionCo/cosubdir || exit 1
test -e cosubdir || { echo "Default workdir name should be last offset path dirname"; exit 1; }
test "`cat cosubdir/subdir_file.txt`" = "Subdir file" || { echo "Offset file contained unexpected content"; exit 1; }
test `ls cosubdir/*.txt | wc -l` = 1 || { echo "Subdir contains unexpected file"; exit 1; }

rm -r cosubdir || exit 1

$BOAR co TestSessionCo/cosubdir/// || { echo "Co failed with spec with ending slashes"; exit 1; }
test -e cosubdir || { echo "Workdir didn't get expected name with spec with ending slashes"; exit 1; }
# Issue 74 - Files missing when checking out workdir with an offset ending with a slash
test -e cosubdir/subdir_file.txt || { echo "Offset workdir with slashes has missing file"; exit 1; }

$BOAR co NonExistingSession && { echo "Co of non-existing session should fail"; exit 1; }
$BOAR co NonExistingSession 2>&1 | grep "ERROR: No such session found: NonExistingSession" || \
    { echo "Unexpected error message for missing session"; exit 1; }

# Issue 73. If sessions are regarded as entries in a directory tree,
# "/Session" should refer to the same entity as "Session".
$BOAR co /NonExistingSession 2>&1 | grep "ERROR: Checkout specification must not start with a slash" || \
    { echo "Unexpected error message for missing session with initial slash"; exit 1; }

$BOAR co -r 6 TestSessionCo should_fail && { echo "Co of non-existing revision should fail"; exit 1; }
$BOAR co -r 6 TestSessionCo should_fail 2>&1 | grep "ERROR: There is no such revision of the given session" || \
    { echo "Unexpected error message for missing session"; exit 1; }
test ! -e should_fail || { echo "Failed co should not create a workdir"; exit 1; }

$BOAR mksession AnotherSession || exit 1
$BOAR co -r 6 AnotherSession || { echo "New session didn't get expected rev"; exit 1; }

# Same tests, but now the revision exists, but in another session
$BOAR co -r 6 TestSessionCo should_fail && { echo "Co of non-existing revision should fail"; exit 1; }
$BOAR co -r 6 TestSessionCo should_fail 2>&1 | grep "ERROR: There is no such revision of the given session" || \
    { echo "Unexpected error message for missing session"; exit 1; }
test ! -e should_fail || { echo "Failed co should not create a workdir"; exit 1; }

exit 0 # All is well
