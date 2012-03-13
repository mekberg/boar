set -e

$BOAR import | grep "Usage: boar import" || { echo "Import with no args should give usage information"; exit 1; }

export REPO_PATH=IMPORT_TEST_REPO
$BOAR mkrepo $REPO_PATH || exit 1
$BOAR mksession TestSession || exit 1
mkdir Import || exit 1
echo "Some data" >Import/file.txt || exit 1

$BOAR import -wq Import TestSession || exit 1

( cd Import && $BOAR status -vq >../status.txt 2>&1 ) || exit 1
head -n -1 status.txt >status_no_timing.txt
diff status_no_timing.txt - <<EOF || { echo "Status gave unexpected output"; exit 1; }
  file.txt
EOF

true

