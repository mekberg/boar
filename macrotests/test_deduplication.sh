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

function fill_repo_and_clone() {
$BOAR --repo="$REPO" mksession Session || exit 1
$BOAR --repo="$REPO" co Session || exit 1

cp $BIGFILE Session/a.bin || exit 1

(cd Session && 
    $BOAR ci -q ) || exit 1

(cd Session && 
    echo "Tjosan" >>a.bin &&
    $BOAR ci -q ) || exit 1

test -d "$REPO/recipes" || exit 1
$BOAR --repo="$REPO" verify || { echo "Verify failed"; exit 1; }

$BOAR clone "$REPO" "$CLONE" || exit 1
test -d "$CLONE/recipes" || exit 1
}

#
# Test that a non-dedup repo (and clone thereof) really isn't deduplicated
#

$BOAR mkrepo "$REPO" || exit 1
fill_repo_and_clone
test -z $(ls -A "$REPO/recipes") || { echo "Recipe dir should be empty for non-dedup repo"; exit 1; }
test -z $(ls -A "$CLONE/recipes") || { echo "Cloned recipe dir should be empty for non-dedup repo"; exit 1; }
rm -r Session "$REPO" "$CLONE" || exit 1

#
# Test that a dedup repo (and clone thereof) really is deduplicated
#

$BOAR mkrepo -d "$REPO" || exit 1
fill_repo_and_clone
test ! -z $(ls -A "$REPO/recipes") || { echo "Recipe dir should NOT be empty for dedup repo"; exit 1; }
test ! -z $(ls -A "$CLONE/recipes") || { echo "Cloned recipe dir should NOT be empty for dedup repo"; exit 1; }
rm -r Session "$REPO" "$CLONE" || exit 1

