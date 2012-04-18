# Test that the truncate command behaves as expected.
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

echo "Yet another file" >AnotherTestSession/yet_another.txt || exit 1
rm AnotherTestSession/another.txt || exit 1
(cd AnotherTestSession && $BOAR ci -q) || exit 1

cp -an TESTREPO TESTREPO_truncated || exit 1
touch TESTREPO_truncated/ENABLE_PERMANENT_ERASE || exit 1


echo --- Verify that all snapshots exist before truncation
for snapshot in 1 2 3 4 5 6 7; do
    # Make sure that all expected snapshots exist before truncation
    test -e "TESTREPO_truncated/sessions/$snapshot" || { echo "Snapshot $snapshot should exist"; exit 1; }
done
test ! -e "TESTREPO_truncated/sessions/8" || { echo "Snapshot should not exist yet"; exit 1; }

cat >snapshot_delete_test_hook.py <<"EOF"
def kill_at_4(rev):
    if rev != 4:
        return
    import sys
    sys.exit(123)
repository._snapshot_delete_test_hook = kill_at_4
EOF

$BOAR --EXEC snapshot_delete_test_hook.py --repo=TESTREPO_truncated truncate TestSession

if [ $? -ne 123 ]; then
    echo "Truncation didn't return expected error code"
    exit 1
fi

grep __deleted TESTREPO_truncated/sessions/3/session.json >/dev/null && { echo "Repo should only be partially truncated"; exit 1; }
grep __deleted TESTREPO_truncated/sessions/6/session.json >/dev/null || { echo "Repo should be partially truncated"; exit 1; }

cat >expected.txt <<EOF
!NOTICE: The repository at .* has pending operations. Resuming...
NOTICE: Pending operations completed.
[1, null, "__deleted", "d41d8cd98f00b204e9800998ecf8427e", null, true]
[2, null, "AnotherTestSession", "d41d8cd98f00b204e9800998ecf8427e", null, false]
[3, null, "__deleted", "d41d8cd98f00b204e9800998ecf8427e", null, true]
[4, null, "__deleted", "d41d8cd98f00b204e9800998ecf8427e", null, true]
[5, 2, "AnotherTestSession", "0e997688909a2d27886dfdeaa627b560", null, false]
[6, null, "__deleted", "d41d8cd98f00b204e9800998ecf8427e", null, true]
[7, 5, "AnotherTestSession", "31a44468d11cc4924b15c5d106410a63", null, false]
[8, null, "TestSession", "ed6b2754f96ba1e3c1cf10ab3e492b03", "Standalone snapshot", false]
!Finished in .* seconds
EOF

$BOAR --repo=TESTREPO_truncated list -d >output.txt 2>&1 || { cat output.txt; echo "Resumption failed"; exit 1; }
txtmatch.py expected.txt output.txt || exit 1

# This verify will access the repo and process the queue before verification
$BOAR --repo=TESTREPO_truncated verify || { echo "Truncated repo failed verify"; exit 1; }

exit 0 # All is well
