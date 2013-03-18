TESTDIR="`pwd`"
REPO=$TESTDIR/DEDUPREPO
CLONE=$TESTDIR/DEDUPCLONE
BIGFILE=$TESTDIR/bigfile.bin
mkrandfile.py 0 1000000 $BIGFILE || exit 1
md5sum -c <<EOF || exit 1
d978f6138c52b8be4f07bbbf571cd450  $BIGFILE
EOF

($BOAR --version | grep "Deduplication module v1.0") || { 
    echo "Deduplication module has wrong version / is not installed"; exit 1; }

(BOAR_DISABLE_DEDUP=1 $BOAR --version | grep "Deduplication module not installed") || { 
    echo "Deduplication module could not be disabled for testing"; exit 1; }

function fill_repo() {
$BOAR --repo="$REPO" mksession Session || exit 1
$BOAR --repo="$REPO" co Session || exit 1

cp $BIGFILE Session/a.bin || exit 1

(cd Session && 
    $BOAR ci -q ) || exit 1

(cd Session && 
    echo "Tjosan" >>a.bin &&
    md5sum a.bin >>manifest.md5 &&
    $BOAR ci -q ) || exit 1

test -d "$REPO/recipes" || exit 1
$BOAR --repo="$REPO" verify || { echo "Verify failed"; exit 1; }

rm -r Session || exit 1
$BOAR --repo="$REPO" co Session || exit 1
(cd Session && md5sum -c manifest.md5) || exit 1
}

function clone_repo() {
$BOAR clone "$REPO" "$CLONE" || exit 1
test -d "$CLONE/recipes" || exit 1
}

#
# Test that a non-dedup repo (and clone thereof) really isn't deduplicated
#

$BOAR mkrepo "$REPO" || exit 1
fill_repo
clone_repo
test -z $(ls -A "$REPO/recipes") || { echo "Recipe dir should be empty for non-dedup repo"; exit 1; }
test -z $(ls -A "$CLONE/recipes") || { echo "Cloned recipe dir should be empty for non-dedup repo"; exit 1; }
rm -r Session "$REPO" "$CLONE" || exit 1

#
# Test that a dedup repo (and clone thereof) really is deduplicated
#

$BOAR mkrepo -d "$REPO" || exit 1
fill_repo
clone_repo
test ! -z $(ls -A "$REPO/recipes") || { echo "Recipe dir should NOT be empty for dedup repo"; exit 1; }
test ! -z $(ls -A "$CLONE/recipes") || { echo "Cloned recipe dir should NOT be empty for dedup repo"; exit 1; }
rm -r Session "$REPO" "$CLONE" || exit 1

#
# Test that a dedup repo cannot be created if the dedup module is
# unavailable
#

BOAR_DISABLE_DEDUP=1 $BOAR mkrepo -d REPO >output.txt 2>&1 &&  { echo "Should not be possible to create dedup repo without dedup module"; exit 1; }
grep "ERROR: Cannot create deduplicated repository: deduplication module is not installed" output.txt || { echo "Unexpected output"; exit 1; }
rm output.txt || exit 1

#
# Test that a dedup repo cannot be committed to if the dedup module is
# unavailable
#

$BOAR mkrepo -d $REPO || exit 1
BOAR_DISABLE_DEDUP=1 $BOAR --repo="$REPO" mksession Session >output.txt 2>&1 && { 
    echo "Should not be possible to create session in dedup repo without the dedup module"; exit 1; }

cat >expected.txt <<EOF
NOTICE: This repository requires the native deduplication module for writing -
        only read operations can be performed.
REPO USAGE ERROR: Repository is read-only
!Finished in .* seconds
EOF

txtmatch.py expected.txt output.txt || {
    echo "Creating session in dedup repo without dedup module gave unexpected error message"; exit 1; }

$BOAR --repo="$REPO" mksession Session || exit 1

BOAR_DISABLE_DEDUP=1 $BOAR --repo="$REPO" co Session >output.txt 2>&1 || { 
    echo "Failed to check out session from dedup repo without dedup module"; exit 1; }

cat >expected.txt <<EOF
NOTICE: This repository requires the native deduplication module for writing -
        only read operations can be performed.
!Checking out to workdir .*
!Finished in .* seconds
EOF

txtmatch.py expected.txt output.txt || {
    echo "Checking out dedup repo without dedup module gave unexpected message"; exit 1; }

( cd Session && echo "Tjohej" >a.txt && 
    BOAR_DISABLE_DEDUP=1 $BOAR ci -q ) >output.txt 2>&1 && { 
    echo "Committing to a dedup repo should fail"; exit 1; }

cat >expected.txt <<EOF
NOTICE: This repository requires the native deduplication module for writing -
        only read operations can be performed.
REPO USAGE ERROR: Repository is read-only
!Finished in .* seconds
EOF

txtmatch.py expected.txt output.txt || {
    echo "Committing in dedup repo without dedup module gave unexpected error message"; exit 1; }

rm -r expected.txt output.txt "$REPO" Session || exit 1

#
# Test cloning from non-dedup to dedup
#

$BOAR mkrepo "$REPO" || exit 1
fill_repo
$BOAR mkrepo -d "$CLONE" || exit 1
$BOAR clone "$REPO" "$CLONE" || exit 1
test -z $(ls -A "$REPO/recipes") || { echo "Non-dedup repo should not have recipes"; exit 1; }
test ! -z $(ls -A "$CLONE/recipes") || { echo "Dedup clone should have recipes"; exit 1; }
rm -r "$REPO" "$CLONE" Session || exit 1

#
# Test cloning from dedup to non-dedup
#

$BOAR mkrepo -d "$REPO" || exit 1
fill_repo
$BOAR mkrepo "$CLONE" || exit 1
$BOAR clone "$REPO" "$CLONE" || exit 1
test ! -z $(ls -A "$REPO/recipes") || { echo "Dedup repo should have recipes"; exit 1; }
test -z $(ls -A "$CLONE/recipes") || { echo "Non-dedup clone should not have recipes"; exit 1; }
rm -r "$REPO" "$CLONE" Session || exit 1

exit 0
