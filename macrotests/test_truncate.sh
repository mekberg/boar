# Test that the truncate command behaves as expected.
set -e

$BOAR mkrepo TESTREPO || exit 1
$BOAR mksession --repo=TESTREPO TestSession || exit 1
$BOAR --repo=TESTREPO co TestSession || exit 1
$BOAR mksession --repo=TESTREPO AnotherTestSession || exit 1
$BOAR --repo=TESTREPO co AnotherTestSession || exit 1

echo "Rev 2" >TestSession/r2.txt || exit 1
(cd TestSession && $BOAR ci -q) || exit 1

rm TestSession/r2.txt || exit 1
echo "Rev 3" >TestSession/r3.txt || exit 1
(cd TestSession && $BOAR ci -q) || exit 1

echo "Another file" >AnotherTestSession/another.txt || exit 1
(cd AnotherTestSession && $BOAR ci -q) || exit 1

rm TestSession/r3.txt || exit 1
echo "Rev 4" >TestSession/r4.txt || exit 1
(cd TestSession && $BOAR ci -q) || exit 1

cat >expected_disallowed_msg.txt <<EOF
ERROR: This repository does not allow destructive changes.
!Finished in .* seconds
EOF

$BOAR --repo=TESTREPO truncate TestSession >disallowed_msg.txt 2>&1 && { 
    cat disallowed_msg.txt; echo "Truncation of protected repo should fail"; exit 1; }
txtmatch.py expected_disallowed_msg.txt disallowed_msg.txt || { 
    echo "Protected repo gave unexpected error message"; exit 1; }

cp -an TESTREPO TESTREPO_truncated || exit 1
touch TESTREPO_truncated/ENABLE_PERMANENT_ERASE || exit 1


echo --- Verify that all snapshots exist before truncation
for snapshot in 1 2 3 4 5 6; do
    # Make sure that all expected snapshots exist before truncation
    test -e "TESTREPO_truncated/sessions/$snapshot" || { echo "Snapshot $snapshot should exist"; exit 1; }
done
test ! -e "TESTREPO_truncated/sessions/7" || { echo "Snapshot should not exist yet"; exit 1; }


echo --- Perform truncate
cat >expected_truncate_msg.txt <<EOF
Session TestSession has been truncated to revision 7
!Finished in .* seconds
EOF

$BOAR --repo=TESTREPO_truncated truncate TestSession >truncate_msg.txt 2>&1 || { 
    cat truncate_msg.txt; echo "Truncation failed"; exit 1; }
txtmatch.py expected_truncate_msg.txt truncate_msg.txt || { 
    echo "Protected repo gave unexpected output for truncate"; exit 1; }


echo --- Verify that deleted snapshots are gone
for snapshot in 1   3 4   6; do
    # Make sure that only the expected snapshots exist after truncation
    test ! -e "TESTREPO_truncated/sessions/$snapshot" || { echo "Snapshot $snapshot should be deleted"; exit 1; }
done
test -e "TESTREPO_truncated/sessions/2" || { echo "Untruncated snapshot 2 should exist"; exit 1; }
test -e "TESTREPO_truncated/sessions/5" || { echo "Untruncated snapshot 5 should exist"; exit 1; }
test -e "TESTREPO_truncated/sessions/7" || { echo "Independent snapshot 7 should exist"; exit 1; }
test ! -e "TESTREPO_truncated/sessions/8" || { echo "Snapshot 7 should not exist"; exit 1; }

cat >expected_list_msg.txt <<EOF
!Revision id 7 .*, 1 files, \(standalone\) Log: Standalone snapshot
!Finished in .* seconds
EOF

echo --- Verify that other session is intact
$BOAR --repo=TESTREPO_truncated list TestSession >list_msg.txt 2>&1 || exit 1
txtmatch.py expected_list_msg.txt list_msg.txt

cat >expected_list_msg2.txt <<EOF
!Revision id 2 .*, 0 files, \(standalone\) Log: <not specified>
!Revision id 5 .*, 1 files, \(delta\) Log: <not specified>
!Finished in .* seconds
EOF

$BOAR --repo=TESTREPO_truncated list AnotherTestSession >list_msg2.txt 2>&1 || exit 1
txtmatch.py expected_list_msg2.txt list_msg2.txt

echo --- Verify truncated repo
$BOAR --repo=TESTREPO_truncated verify || { echo "Truncated repo failed verify"; exit 1; }

exit 0 # All is well
