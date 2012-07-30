# Test that the clone command behaves as expected.

$BOAR mkrepo TESTREPO || exit 1
$BOAR mksession --repo=TESTREPO TestSession || exit 1
$BOAR --repo=TESTREPO co TestSession || exit 1

echo "Rev 2" >TestSession/r2.txt || exit 1
(cd TestSession && $BOAR ci -q -m"Log message uno" ) || exit 1

rm TestSession/r2.txt || exit 1
echo "Rev 3" >TestSession/r3.txt || exit 1
(cd TestSession && $BOAR ci -q -m"Log message räksmörgås") || exit 1

rm TestSession/r3.txt || exit 1
echo "Rev 4" >TestSession/r4.txt || exit 1
(cd TestSession && $BOAR ci -q -m"Log message plain and simple" ) || exit 1

cat > expected_original_repo_log.txt <<EOF
!Revision id 1 \(.*\), 0 files, \(standalone\) Log: <not specified>
!Revision id 2 \(.*\), 1 files, \(delta\) Log: Log message uno
!Revision id 3 \(.*\), 1 files, \(delta\) Log: Log message räksmörgås
!Revision id 4 \(.*\), 1 files, \(standalone\) Log: Log message plain and simple
EOF

$BOAR --repo=TESTREPO list TestSession |grep -v "Finished" >original_repo_log.txt || exit 1
txtmatch.py expected_original_repo_log.txt original_repo_log.txt  || { echo "Unexpected log contents before cloning"; exit 1; }
sleep 1 # Ensure that we'll notice if log times changes during clone

$BOAR clone TESTREPO TESTREPO_clone || { echo "Cloning to new repo failed"; exit 1; }
$BOAR clone TESTREPO TESTREPO_clone || { echo "Cloning between identical repos should succeed (1)"; exit 1; }
$BOAR clone TESTREPO_clone TESTREPO || { echo "Cloning between identical repos should succeed (2)"; exit 1; }

$BOAR --repo=TESTREPO_clone list TestSession |grep -v "Finished" >clone_repo_log.txt || exit 1
txtmatch.py original_repo_log.txt clone_repo_log.txt || { echo "Clone log messages/time differs from original"; exit 1; }

echo "New file" >TestSession/new_file.txt || exit 1
(cd TestSession && $BOAR ci -q) || exit 1

$BOAR clone TESTREPO_clone TESTREPO && { echo "Non-continuation cloning should fail"; exit 1; }
$BOAR clone TESTREPO_clone TESTREPO 2>&1| grep "ERROR: The source repo is not a continuation" || { echo "Non-continuation cloning had unexpected error message"; exit 1; }
$BOAR clone TESTREPO TESTREPO_clone || { echo "Update of cloned repo failed"; exit 1; }

$BOAR clone TESTREPO_clone TESTREPO_clone2 || { echo "Second clone failed"; exit 1; }

$BOAR clone TESTREPO TESTREPO_corrupted || { echo "Cloning failed"; exit 1; }
rm TESTREPO_corrupted/blobs/64/64c1fdc8fa4f740f95f3274707726d7c || exit 1
$BOAR clone TESTREPO_corrupted TESTREPO_corrupted_clone && { echo "Cloning of corrupted repo should fail"; exit 1; }

exit 0 # All is well
