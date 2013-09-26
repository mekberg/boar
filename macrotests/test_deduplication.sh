if [ "$BOAR_SKIP_DEDUP_TESTS" == "1" ]; then
    echo "Skipping due to BOAR_SKIP_DEDUP_TESTS"
    exit 0
fi

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

function dir_empty() {
    # Returns true if the given directory is empty
    d="$1"
    test -d "$d" || { echo "$d is not an existing directory"; exit 1; }
    ! (ls -A "$d" | grep . >/dev/null)
}

function fill_repo() {
$BOAR --repo="$REPO" mksession Session || exit 1
$BOAR --repo="$REPO" co Session || exit 1

cp $BIGFILE Session/a.bin || exit 1

(cd Session && 
    $BOAR ci -q ) || exit 1

(cd Session && 
    echo "Tjosan" >>a.bin &&
    md5sum a.bin >manifest.md5 &&
    $BOAR ci -q ) || exit 1

(cd Session && 
    echo "Tjosan2" >>a.bin &&
    md5sum a.bin >manifest.md5 &&
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
dir_empty "$REPO/recipes" || { echo "Recipe dir should be empty for non-dedup repo"; exit 1; }
dir_empty "$CLONE/recipes" || { echo "Cloned recipe dir should be empty for non-dedup repo"; exit 1; }
rm -r Session "$REPO" "$CLONE" || exit 1

#
# Test that a dedup repo (and clone thereof) really is deduplicated
#

$BOAR mkrepo -d "$REPO" || exit 1
fill_repo
clone_repo
dir_empty "$REPO/recipes" && { echo "Recipe dir should NOT be empty for dedup repo"; exit 1; }
dir_empty "$CLONE/recipes" && { echo "Cloned recipe dir should NOT be empty for dedup repo"; exit 1; }
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
echo "Creating forbidden session..."
BOAR_DISABLE_DEDUP=1 $BOAR --repo="$REPO" mksession Session >output.txt 2>&1 && { 
    cat output.txt; echo "Should not be possible to create session in dedup repo without the dedup module"; exit 1; }

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
dir_empty "$REPO/recipes" || { echo "Non-dedup repo should not have recipes"; exit 1; }
dir_empty "$CLONE/recipes" && { echo "Dedup clone should have recipes"; exit 1; }
rm -r "$REPO" "$CLONE" Session || exit 1

#
# Test cloning from dedup to non-dedup
#

$BOAR mkrepo -d "$REPO" || exit 1
fill_repo
$BOAR mkrepo "$CLONE" || exit 1
$BOAR clone "$REPO" "$CLONE" || exit 1
dir_empty "$REPO/recipes" && { echo "Dedup repo should have recipes"; exit 1; }
dir_empty "$CLONE/recipes" || { echo "Non-dedup clone should not have recipes"; exit 1; }
rm -r "$REPO" "$CLONE" Session || exit 1

#
# Test truncation of deduplicated repo
#


$BOAR mkrepo -d "$REPO" || exit 1
fill_repo
touch $REPO/ENABLE_PERMANENT_ERASE || exit 1
test -e $REPO/recipes/90/90d077e8f5d08222620ffc97bee8a19a.recipe || exit 1 # The previous one (should be culled)
test -e $REPO/recipes/7e/7efcbecf434ce1588570132fa61f53c6.recipe || exit 1 # The last one (should remain)

$BOAR --repo="$REPO" truncate Session || exit 1

test ! -e $REPO/recipes/90/90d077e8f5d08222620ffc97bee8a19a.recipe || { echo "Should have been removed by truncate"; exit 1; }
test -e $REPO/recipes/7e/7efcbecf434ce1588570132fa61f53c6.recipe || { echo "Should remain after truncate"; exit 1; }
$BOAR --repo="$REPO" verify || { echo "Verify failed"; exit 1; }
rm -r "Session" "$REPO"

#
# Test truncation followed by commit of re-added truncated data. If
# the blocksdb hasn't been purged correctly, the generated recipes
# will be invalid.
#

$BOAR mkrepo -d "$REPO" || exit 1
$BOAR --repo="$REPO" mksession Session || exit 1
$BOAR --repo="$REPO" co Session || exit 1
cp $BIGFILE Session/a.bin || exit 1
(cd Session && $BOAR ci -q ) || exit 1
rm Session/a.bin || exit 1
(cd Session && $BOAR ci -q ) || exit 1
touch $REPO/ENABLE_PERMANENT_ERASE || exit 1
$BOAR --repo="$REPO" truncate Session || exit 1
(cd Session && $BOAR update -q ) || exit 1
cp $BIGFILE Session/b.bin || exit 1
(cd Session && $BOAR ci -q ) || exit 1
$BOAR --repo="$REPO" verify || { echo "Verify failed"; exit 1; }
rm -r "Session" "$REPO"

#
# Test missing recipe
#

$BOAR mkrepo -d "$REPO" || exit 1
fill_repo
rm $REPO/recipes/90/90d077e8f5d08222620ffc97bee8a19a.recipe
$BOAR --repo="$REPO" verify | grep "REPO CORRUPTION: Snapshot 3 is missing blob 90d077e8f5d08222620ffc97bee8a19a" || 
{ echo "Verify of missing recipe repo gave unexpected message"; exit 1; }
rm -r "Session" "$REPO"

#
# Test corrupt recipe
#

$BOAR mkrepo -d "$REPO" || exit 1
fill_repo
cat $REPO/recipes/90/90d077e8f5d08222620ffc97bee8a19a.recipe
echo "Räksmörgås" >$REPO/recipes/90/90d077e8f5d08222620ffc97bee8a19a.recipe
$BOAR --repo="$REPO" verify >output.txt 2>&1 && { echo "Verify for corrupt recipe should fail"; exit 1; }
grep "REPO CORRUPTION: Recipe is malformed" output.txt || { 
    cat output.txt; echo "Verify for corrupt recipe gave unexpected output"; exit 1; }
rm -r "Session" "$REPO"

#
# Test well-formed recipe containing wrong md5sum attribute
#

$BOAR mkrepo -d "$REPO" || exit 1
fill_repo
sed -i 's/90d077e8f5d08222620ffc97bee8a19a/00000000000000000000000000000000/g' \
    $REPO/recipes/90/90d077e8f5d08222620ffc97bee8a19a.recipe
$BOAR --repo="$REPO" verify >output.txt 2>&1 && { echo "Verify for corrupt recipe should fail"; exit 1; }
grep "REPO CORRUPTION: Recipe name does not match recipe contents" output.txt || { 
    cat output.txt; echo "Verify for wrong md5sum attribute recipe gave unexpected output"; exit 1; }
rm -r "Session" "$REPO"

#
# Test recipe with wrong output size
#

$BOAR mkrepo -d "$REPO" || exit 1
fill_repo
sed -i 's/16967/16966/g' \
    $REPO/recipes/90/90d077e8f5d08222620ffc97bee8a19a.recipe
$BOAR --repo="$REPO" verify >output.txt 2>&1 && { echo "Verify for wrong size recipe should fail"; exit 1; }
grep "REPO CORRUPTION: Recipe is internally inconsistent" output.txt || { 
    cat output.txt; echo "Verify for wrong size recipe gave unexpected output"; exit 1; }
rm -r "Session" "$REPO"

#
# Test valid but sneaky recipe yielding wrong output stream
#

$BOAR mkrepo -d "$REPO" || exit 1
fill_repo
sed -i 's/1ac15243e714d0b5d32779f6c7f2d8fa/d978f6138c52b8be4f07bbbf571cd450/g' \
    $REPO/recipes/90/90d077e8f5d08222620ffc97bee8a19a.recipe
$BOAR --repo="$REPO" verify >output.txt 2>&1 && { echo "Verify for sneaky recipe should fail"; exit 1; }
grep "REPO CORRUPTION: Blob corrupted: 90d077e8f5d08222620ffc97bee8a19a" output.txt || { 
    cat output.txt; echo "Verify for sneaky recipe gave unexpected output"; exit 1; }
rm -r "Session" "$REPO"

#
# Test missing attributes
#
$BOAR mkrepo -d "$REPO" || exit 1
fill_repo
sed -i 's/md5sum/missing/g' \
    $REPO/recipes/90/90d077e8f5d08222620ffc97bee8a19a.recipe
$BOAR --repo="$REPO" verify >output.txt 2>&1 && { echo "Verify for corrupt recipe should fail"; exit 1; }
grep "REPO CORRUPTION: Recipe is missing properties" output.txt || { 
    cat output.txt; echo "Verify for missing attributes gave unexpected output"; exit 1; }
rm -r "Session" "$REPO"

exit 0
