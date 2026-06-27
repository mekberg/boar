# Tests for the "maximum blob size" feature: files larger than the
# configured limit are split into several smaller blobs tied together
# with a recipe, so that the repository can live on a filesystem with a
# maximum file size.

TESTDIR="`pwd`"
REPO=$TESTDIR/repo
BIGFILE=$TESTDIR/bigfile.bin

MAX=102400 # 100 KiB, the limit used for $REPO

# A deterministic ~1 MB file (same one used by test_recipes.sh).
python3 "${BOARTESTHOME}/mkrandfile.py" 0 1000000 $BIGFILE || exit 1
md5sum -c <<EOF || exit 1
d978f6138c52b8be4f07bbbf571cd450  $BIGFILE
EOF
BIGMD5=d978f6138c52b8be4f07bbbf571cd450

assert_no_blob_over () {
    # assert_no_blob_over <repo> <limit-in-bytes>
    local repo="$1"; local limit="$2"
    local toobig
    toobig=`find "$repo/blobs" -type f -size +${limit}c`
    if [ -n "$toobig" ]; then
        echo "*** FAIL: found blob(s) larger than $limit bytes in $repo:"
        find "$repo/blobs" -type f -size +${limit}c -printf '%s %p\n'
        exit 1
    fi
}

############################################################
echo "*** Splitting without deduplication"

$BOAR mkrepo --max-file-size 100k $REPO || exit 1
test "`cat $REPO/maxblobsize.txt`" = "102400" || { echo "Wrong maxblobsize.txt contents"; exit 1; }

$BOAR --repo=$REPO mksession Big || exit 1
$BOAR --repo=$REPO co Big || exit 1
(cd Big &&
    cp $BIGFILE bigfile.bin &&
    md5sum bigfile.bin >manifest.md5 &&
    $BOAR ci -q ) || exit 1

assert_no_blob_over $REPO $MAX
# The oversized file must be stored as a recipe, not a raw blob.
test -e $REPO/recipes/d9/$BIGMD5.recipe || { echo "Expected recipe is missing"; exit 1; }
test ! -e $REPO/blobs/d9/$BIGMD5 || { echo "Oversized file should not be a raw blob"; exit 1; }

$BOAR --repo=$REPO verify || { echo "Verify failed"; exit 1; }
rm -r Big || exit 1
$BOAR --repo=$REPO co Big || { echo "Check-out failed"; exit 1; }
(cd Big && md5sum -c manifest.md5 ) || exit 1
rm -r Big || exit 1

############################################################
echo "*** A small file stays a single raw blob"

(cd /tmp && true) # no-op to keep structure clear
$BOAR --repo=$REPO co Big || exit 1
(cd Big &&
    head -c 1000 $BIGFILE >small.bin &&
    SMALLMD5=`md5sum small.bin | cut -d' ' -f1` &&
    md5sum bigfile.bin small.bin >manifest.md5 &&
    $BOAR ci -q &&
    test -e $REPO/blobs/${SMALLMD5:0:2}/$SMALLMD5 || { echo "Small file should be a raw blob"; exit 1; }
    test ! -e $REPO/recipes/${SMALLMD5:0:2}/$SMALLMD5.recipe || { echo "Small file should not have a recipe"; exit 1; }
) || exit 1
assert_no_blob_over $REPO $MAX
$BOAR --repo=$REPO verify || { echo "Verify failed"; exit 1; }
rm -r Big || exit 1

############################################################
echo "*** Cloning a split repo into a plain repo reassembles the file"

CLONE_PLAIN=$TESTDIR/clone_plain
$BOAR clone $REPO $CLONE_PLAIN || { echo "Clone failed"; exit 1; }
test ! -e $CLONE_PLAIN/maxblobsize.txt || { echo "Plain clone unexpectedly has a max blob size"; exit 1; }
# Without a limit, the big file is stored as a single raw blob.
test -e $CLONE_PLAIN/blobs/d9/$BIGMD5 || { echo "Expected reassembled raw blob in plain clone"; exit 1; }
test ! -e $CLONE_PLAIN/recipes/d9/$BIGMD5.recipe || { echo "Plain clone should not have a recipe"; exit 1; }
$BOAR --repo=$CLONE_PLAIN verify || { echo "Plain clone verify failed"; exit 1; }
$BOAR --repo=$CLONE_PLAIN co Big || { echo "Plain clone checkout failed"; exit 1; }
(cd Big && md5sum -c manifest.md5 ) || exit 1
rm -r Big || exit 1

############################################################
echo "*** Cloning into a repo with a (different) limit re-splits the file"

CLONE_SPLIT=$TESTDIR/clone_split
$BOAR mkrepo --max-file-size 70k $CLONE_SPLIT || exit 1
$BOAR clone $REPO $CLONE_SPLIT || { echo "Clone (split) failed"; exit 1; }
assert_no_blob_over $CLONE_SPLIT 71680
test -e $CLONE_SPLIT/recipes/d9/$BIGMD5.recipe || { echo "Re-split clone is missing the recipe"; exit 1; }
$BOAR --repo=$CLONE_SPLIT verify || { echo "Re-split clone verify failed"; exit 1; }
$BOAR --repo=$CLONE_SPLIT co Big || { echo "Re-split clone checkout failed"; exit 1; }
(cd Big && md5sum -c manifest.md5 ) || exit 1
rm -r Big $CLONE_PLAIN $CLONE_SPLIT $REPO || exit 1

############################################################
if [ "$BOAR_SKIP_DEDUP_TESTS" == "1" ]; then
    echo "Skipping deduplication part due to BOAR_SKIP_DEDUP_TESTS"
    exit 0
fi

echo "*** Splitting combined with deduplication"

$BOAR mkrepo --enable-deduplication --max-file-size 100k $REPO || exit 1
$BOAR --repo=$REPO mksession Dedup || exit 1
$BOAR --repo=$REPO co Dedup || exit 1
(cd Dedup &&
    cp $BIGFILE a.bin &&
    $BOAR ci -q ) || exit 1
raw_after_first=`find $REPO/blobs -type f | wc -l`

(cd Dedup &&
    ( echo "a unique short prefix"; cat $BIGFILE ) >b.bin &&
    md5sum a.bin b.bin >manifest.md5 &&
    $BOAR ci -q ) || exit 1
raw_after_second=`find $REPO/blobs -type f | wc -l`

assert_no_blob_over $REPO $MAX
# Deduplication should keep the number of new raw blobs small, even
# though the shared body is stored split across several sub-blobs.
new_blobs=$((raw_after_second - raw_after_first))
echo "New raw blobs from the near-identical second file: $new_blobs"
if [ "$new_blobs" -gt 3 ]; then
    echo "*** FAIL: deduplication across split boundaries did not work ($new_blobs new blobs)"
    exit 1
fi

$BOAR --repo=$REPO verify || { echo "Dedup verify failed"; exit 1; }
rm -r Dedup || exit 1
$BOAR --repo=$REPO co Dedup || { echo "Dedup checkout failed"; exit 1; }
(cd Dedup && md5sum -c manifest.md5 ) || exit 1
rm -r Dedup $REPO || exit 1

exit 0
