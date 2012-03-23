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

cat >pause_at_commit.py <<"EOF"
def kill_at_4(rev):
    if rev != 4:
        return
    import sys
    sys.exit(123)
repository._snapshot_delete_test_hook = kill_at_4
EOF

$BOAR --EXEC pause_at_commit.py --repo=TESTREPO_truncated truncate TestSession

if [ $? -ne 123 ]; then
    echo "Truncation didn't return expected error code"
    exit 1
fi

for snapshot in 4 6 8; do
    # These snapshots should be gone by now (no 4 halfway)
    test ! -e "TESTREPO_truncated/sessions/$snapshot" || { echo "Snapshot $snapshot should be deleted"; exit 1; }
done

for snapshot in 1 2 3   5 7; do
    # These snapshots should still exist since operation was aborted
    # before 1 2 3 was deleted and the new base snapshot could be
    # created.
    test -e "TESTREPO_truncated/sessions/$snapshot" || { echo "Snapshot $snapshot should still exist"; exit 1; }
done

# This verify will access the repo and process the queue before verification
$BOAR --repo=TESTREPO_truncated verify || { echo "Truncated repo failed verify"; exit 1; }

for snapshot in 1 3 4 6 9; do
    test ! -e "TESTREPO_truncated/sessions/$snapshot" || { echo "Snapshot $snapshot should not exist"; exit 1; }
done

for snapshot in 5 7 8; do
    test -e "TESTREPO_truncated/sessions/$snapshot" || { echo "Snapshot $snapshot should still exist"; exit 1; }
done


exit 0 # All is well
