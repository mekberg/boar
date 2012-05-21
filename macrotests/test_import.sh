set -e

$BOAR import | grep "Usage: boar import" || { echo "Import with no args should give usage information"; exit 1; }

export REPO_PATH=IMPORT_TEST_REPO
$BOAR mkrepo $REPO_PATH || exit 1
$BOAR mksession TestSession || exit 1
mkdir Import || exit 1
echo "Some data" >Import/file.txt || exit 1

echo --- Test normal import
cat >expected.txt <<EOF
Sending file.txt
Checked in session id 2
!Finished in (.*) seconds
EOF

$BOAR import -wq Import TestSession >output.txt 2>&1 || exit 1

txtmatch.py expected.txt output.txt || {
    echo "Import gave unexpected message"; exit 1; }

echo --- Test unchanged import
cat >expected.txt <<EOF
NOTICE: Didn't find any new or changed files to import.
!Finished in (.*) seconds
EOF

$BOAR import -wq Import TestSession >output.txt 2>&1 || exit 1

txtmatch.py expected.txt output.txt || {
    echo "Unchanged import gave unexpected message"; exit 1; }

echo --- Test unchanged import with --allow-empty
cat >expected.txt <<EOF
Checked in session id 3
!Finished in (.*) seconds
EOF

$BOAR import --allow-empty -wq Import TestSession >output.txt 2>&1 || exit 1

txtmatch.py expected.txt output.txt || {
    echo "Unchanged import --allow-empty gave unexpected message"; exit 1; }

echo --- Test contents

( cd Import && $BOAR status -vq >../status.txt 2>&1 ) || exit 1
head -n -1 status.txt >status_no_timing.txt
diff status_no_timing.txt - <<EOF || { echo "Status gave unexpected output"; exit 1; }
  file.txt
EOF

true

