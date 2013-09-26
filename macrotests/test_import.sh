set -e

$BOAR import | grep "Usage: boar import" || { echo "Import with no args should give usage information"; exit 1; }

export REPO_PATH=IMPORT_TEST_REPO
$BOAR mkrepo $REPO_PATH || exit 1
$BOAR mksession TestSession || exit 1
mkdir Import || exit 1
echo "Some data" >Import/file.txt || exit 1

echo --- Test dry-run import
cat >expected.txt <<EOF
Sending file.txt
Verifying and integrating commit
NOTICE: Nothing was imported.
!Finished in (.*) seconds
EOF

$BOAR import -nq Import TestSession >output.txt 2>&1 || exit 1
test -e Import/.boar && { echo "Dry-run should not create workdir"; exit 1; }
txtmatch.py expected.txt output.txt || {
    cat output.txt; echo "Dry-run import gave unexpected message"; exit 1; }
rm output.txt || exit 1

echo --- Test normal import
cat >expected.txt <<EOF
Sending file.txt
Verifying and integrating commit
Checked in session id 2
!Finished in (.*) seconds
EOF

$BOAR import -wq Import TestSession >output.txt 2>&1 || exit 1
test -e Import/.boar || { echo "Normal import should create a workdir"; exit 1; }
txtmatch.py expected.txt output.txt || {
    echo "Import gave unexpected message"; exit 1; }

cat >expected.txt <<EOF
!Finished in .* seconds
EOF

(cd Import && $BOAR status -q) >output.txt 2>&1 || { 
    cat output.txt; echo "Workdir status after import -w failed"; exit 1; }
txtmatch.py expected.txt output.txt || { 
    echo "Unexpected output for workdir status after import -w"; exit 1; }

echo --- Test unchanged import
rm -r Import/.boar || exit 1
cat >expected.txt <<EOF
NOTICE: Nothing was imported.
!Finished in (.*) seconds
EOF

$BOAR import -q Import TestSession >output.txt 2>&1 || { cat output.txt; exit 1; }

txtmatch.py expected.txt output.txt || {
    echo "Unchanged import gave unexpected message"; exit 1; }

echo --- Test unchanged import with --allow-empty
rm -r Import/.boar || exit 1
cat >expected.txt <<EOF
Verifying and integrating commit
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

# Issue 61: AssertionError when importing with an offset ending with a slash
mkdir MoreImport || exit 1
echo "More data" >MoreImport/another_file.txt || exit 1
$BOAR import -Wq MoreImport TestSession/subpathwithslash/ || 
{ echo "Error when importing to offset path with ending slash"; exit 1; }


echo --- Test the order of imported files.
# Issue 53:Import file order should be in some non-random order
cat >expected.txt <<EOF
Sending abc/aadvark.txt
Sending abc/bumblebee.txt
Sending abc/cobra.txt
Sending abc/dodo.txt
Sending abc/elephant.txt
Verifying and integrating commit
Checked in session id 5
!Finished in (.*) seconds
EOF

mkdir Abc || exit 1

date >Abc/cobra.txt
date >Abc/dodo.txt
date >Abc/elephant.txt
date >Abc/aadvark.txt
date >Abc/bumblebee.txt

$BOAR import -Wq Abc TestSession/abc >output.txt 2>&1 || exit 1

txtmatch.py expected.txt output.txt || {
    cat output.txt; echo "Abc import gave unexpected message"; exit 1; }

echo --- Test workdir creation options

mkdir NotWorkdir || exit 1
echo "Avocado" >NotWorkdir/newfile.txt || exit 1

$BOAR import -wWq NotWorkdir TestSession/notworkdir && { echo "Conflicting workdir options should fail"; exit 1; }
test -e NotWorkdir/.boar && { echo "Conflicting workdir options should not create a workdir"; exit 1; }

$BOAR import -Wq NotWorkdir TestSession/notworkdir1 || { echo "Import with --no-workdir option failed"; exit 1; }
test -e NotWorkdir/.boar && { echo "Import with --no-workdir should not create a workdir"; exit 1; }

$BOAR import -nq NotWorkdir TestSession/notworkdir1 || { echo "Import with --dry-run option failed"; exit 1; }
test -e NotWorkdir/.boar && { echo "Import with --dry-run should not create a workdir"; exit 1; }

$BOAR import -wq NotWorkdir TestSession/notworkdir2 || { echo "Import with --create-workdir option failed"; exit 1; }
test -e NotWorkdir/.boar || { echo "Import with explicit workdir creation should create a workdir"; exit 1; }
rm -r NotWorkdir/.boar || exit 1

$BOAR import -q NotWorkdir TestSession/notworkdir3 || { echo "Import without options failed"; exit 1; }
test -e NotWorkdir/.boar || { echo "Import with no options should create a workdir"; exit 1; }

$BOAR import -q NotWorkdir TestSession/notworkdir4 && { echo "Repeated import should fail"; exit 1; }

true

