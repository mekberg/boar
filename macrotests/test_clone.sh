# Test that the clone command behaves as expected.

$BOAR mkrepo TESTREPO || exit 1
$BOAR mksession --repo=TESTREPO TestSession || exit 1
$BOAR --repo=TESTREPO co TestSession || exit 1

echo "Rev 2" >TestSession/r2.txt || exit 1
(cd TestSession && $BOAR ci -q) || exit 1

rm TestSession/r2.txt || exit 1
echo "Rev 3" >TestSession/r3.txt || exit 1
(cd TestSession && $BOAR ci -q) || exit 1

rm TestSession/r3.txt || exit 1
echo "Rev 4" >TestSession/r4.txt || exit 1
(cd TestSession && $BOAR ci -q) || exit 1


$BOAR clone TESTREPO TESTREPO_clone || { echo "Cloning to new repo failed"; exit 1; }
$BOAR clone TESTREPO TESTREPO_clone || { echo "Cloning between identical repos should succeed"; exit 1; }
$BOAR clone TESTREPO_clone TESTREPO || { echo "Cloning between identical repos should succeed"; exit 1; }

echo "New file" >TestSession/new_file.txt || exit 1
(cd TestSession && $BOAR ci -q) || exit 1

$BOAR clone TESTREPO_clone TESTREPO && { echo "Non-continuation cloning should fail"; exit 1; }
$BOAR clone TESTREPO_clone TESTREPO 2>&1| grep "ERROR: The source repo is not a continuation" || { echo "Non-continuation cloning had unexpected error message"; exit 1; }
$BOAR clone TESTREPO TESTREPO_clone || { echo "Update of cloned repo failed"; exit 1; }

$BOAR clone TESTREPO_clone TESTREPO_clone2 || { echo "Second clone failed"; exit 1; }

exit 0 # All is well
