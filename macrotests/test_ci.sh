set -e

$BOAR ci | grep "ERROR: This directory is not a boar workdir" || { echo "Ci with no args should give usage information"; exit 1; }

export REPO_PATH=CI_TEST_REPO
$BOAR mkrepo $REPO_PATH || exit 1
$BOAR mksession Test || exit 1
$BOAR co Test
echo "Some data" >Test/file.txt || exit 1

echo --- Test normal ci
cat >expected.txt <<EOF
Sending file.txt
Verifying and integrating commit
Checked in session id 2
!Finished in (.*) seconds
EOF

(cd Test; $BOAR ci -q) >output.txt 2>&1 || { cat output.txt; exit 1; }

txtmatch.py expected.txt output.txt || {
    echo "Ci gave unexpected message"; exit 1; }

echo --- Test unchanged ci
cat >expected.txt <<EOF
NOTICE: Didn't find any changes to check in.
!Finished in (.*) seconds
EOF

(cd Test; $BOAR ci -q) >output.txt 2>&1 || exit 1

txtmatch.py expected.txt output.txt || {
    echo "Unchanged ci gave unexpected message"; exit 1; }

echo --- Test unchanged ci with --allow-empty
cat >expected.txt <<EOF
Verifying and integrating commit
Checked in session id 3
!Finished in (.*) seconds
EOF

(cd Test; $BOAR ci --allow-empty -q) >output.txt 2>&1 || exit 1

txtmatch.py expected.txt output.txt || {
    echo "Unchanged ci --allow-empty gave unexpected message"; exit 1; }

echo --- Test contents

( cd Test && $BOAR status -vq >../status.txt 2>&1 ) || exit 1
head -n -1 status.txt >status_no_timing.txt
diff status_no_timing.txt - <<EOF || { echo "Status gave unexpected output"; exit 1; }
  file.txt
EOF

echo --- Test the order of ci 
# Issue 53:Import file order should be in some non-random order
cat >expected.txt <<EOF
Sending Abc/aadvark.txt
Sending Abc/bumblebee.txt
Sending Abc/cobra.txt
Sending Abc/dodo.txt
Sending Abc/elephant.txt
Verifying and integrating commit
Checked in session id 4
!Finished in (.*) seconds
EOF

cd Test || exit 1
mkdir Abc || exit 1
date >Abc/cobra.txt
date >Abc/dodo.txt
date >Abc/elephant.txt
date >Abc/aadvark.txt
date >Abc/bumblebee.txt
cd .. || exit 1

(cd Test; $BOAR ci -q) >output.txt 2>&1 || exit 1

txtmatch.py expected.txt output.txt || {
    cat output.txt; echo "Checkin order test gave unexpected message"; exit 1; }

true

