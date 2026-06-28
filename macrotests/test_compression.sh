# Tests for the blob compression feature: a repository may store all blob
# data compressed with a chosen algorithm, described by a "compress" recipe.

TESTDIR="`pwd`"
BIGFILE=$TESTDIR/bigfile.bin

# A deterministic ~1 MB file (same one used by test_recipes.sh).
python3 "${BOARTESTHOME}/mkrandfile.py" 0 1000000 $BIGFILE || exit 1
md5sum -c <<EOF || exit 1
d978f6138c52b8be4f07bbbf571cd450  $BIGFILE
EOF
BIGMD5=d978f6138c52b8be4f07bbbf571cd450

# gzip and xz are always available (Python standard library). lz4 needs the
# optional module - test it only when present.
ALGOS="gzip xz"
if python3 -c "import lz4.frame" 2>/dev/null; then
    ALGOS="$ALGOS lz4"
fi

for ALGO in $ALGOS; do
    echo "*** Compression algorithm: $ALGO"
    REPO=$TESTDIR/repo_$ALGO
    $BOAR mkrepo --compress $ALGO $REPO || exit 1
    test "`cat $REPO/compression.txt`" = "$ALGO" || { echo "Wrong compression.txt for $ALGO"; exit 1; }

    $BOAR --repo=$REPO mksession S || exit 1
    $BOAR --repo=$REPO co S || exit 1
    (cd S &&
        cp $BIGFILE big.bin &&
        printf 'small compressible text, repeated. ' >small.txt &&
        for i in $(seq 1 100); do printf 'small compressible text, repeated. ' >>small.txt; done &&
        md5sum big.bin small.txt >manifest.md5 &&
        $BOAR ci -q ) || exit 1

    # The big file must be stored as a "compress" recipe, not a raw blob.
    RECIPE=$REPO/recipes/d9/$BIGMD5.recipe
    test -e "$RECIPE" || { echo "Expected compress recipe missing for $ALGO"; exit 1; }
    test ! -e $REPO/blobs/d9/$BIGMD5 || { echo "Oversized file should not be a raw blob ($ALGO)"; exit 1; }
    python3 -c "import json,sys; r=json.load(open('$RECIPE')); sys.exit(0 if r['method']=='compress' and r['algorithm']=='$ALGO' else 1)" \
        || { echo "Recipe method/algorithm wrong for $ALGO"; exit 1; }

    # The small, highly compressible file must actually shrink on disk.
    SMALLMD5=`md5sum S/small.txt | cut -d' ' -f1`
    SMALLRECIPE=$REPO/recipes/${SMALLMD5:0:2}/$SMALLMD5.recipe
    stored=`python3 -c "import json,os; r=json.load(open('$SMALLRECIPE')); print(sum(os.path.getsize('$REPO/blobs/'+p['source'][:2]+'/'+p['source']) for p in r['pieces']))"`
    orig=`stat -c%s S/small.txt`
    test "$stored" -lt "$orig" || { echo "Compressible file did not shrink ($ALGO): $orig -> $stored"; exit 1; }

    $BOAR --repo=$REPO verify || { echo "Verify failed ($ALGO)"; exit 1; }
    rm -r S || exit 1
    $BOAR --repo=$REPO co S || { echo "Checkout failed ($ALGO)"; exit 1; }
    (cd S && md5sum -c manifest.md5 ) || exit 1
    rm -r S || exit 1
done

############################################################
echo "*** A gzip source blob is a standard .gz, recoverable with gunzip"

REPO=$TESTDIR/repo_recover
$BOAR mkrepo --compress gzip $REPO || exit 1
$BOAR --repo=$REPO mksession S >/dev/null || exit 1
$BOAR --repo=$REPO co S >/dev/null || exit 1
(cd S && printf 'recover me with standard tools\n' >note.txt && $BOAR ci -q ) || exit 1
NOTEMD5=`md5sum S/note.txt | cut -d' ' -f1`
SRC=`python3 -c "import json; print(json.load(open('$REPO/recipes/${NOTEMD5:0:2}/$NOTEMD5.recipe'))['pieces'][0]['source'])"`
gunzip -c $REPO/blobs/${SRC:0:2}/$SRC >recovered.txt || { echo "gunzip of source blob failed"; exit 1; }
diff S/note.txt recovered.txt || { echo "gunzip recovery mismatch"; exit 1; }
rm -r S $REPO recovered.txt || exit 1

############################################################
echo "*** Compression combined with a maximum blob size splits the compressed stream"

REPO=$TESTDIR/repo_split
$BOAR mkrepo --compress gzip --max-file-size 64k $REPO || exit 1
$BOAR --repo=$REPO mksession S >/dev/null || exit 1
$BOAR --repo=$REPO co S >/dev/null || exit 1
# The big random file barely compresses, so the compressed stream still
# exceeds 64k and must be split into several sub-blobs.
(cd S && cp $BIGFILE big.bin && md5sum big.bin >manifest.md5 && $BOAR ci -q ) || exit 1
if [ -n "`find $REPO/blobs -type f -size +65536c`" ]; then
    echo "Found a blob larger than the 64k limit:"; find $REPO/blobs -type f -size +65536c -printf '%s %p\n'; exit 1
fi
$BOAR --repo=$REPO verify || { echo "Verify (compress+split) failed"; exit 1; }
rm -r S || exit 1
$BOAR --repo=$REPO co S || { echo "Checkout (compress+split) failed"; exit 1; }
(cd S && md5sum -c manifest.md5 ) || exit 1
rm -r S || exit 1

############################################################
echo "*** Cloning a compressed repo into a plain repo reassembles the data"

CLONE=$TESTDIR/clone_plain
$BOAR clone $REPO $CLONE || { echo "Clone failed"; exit 1; }
test ! -e $CLONE/compression.txt || { echo "Plain clone unexpectedly compressed"; exit 1; }
$BOAR --repo=$CLONE verify || { echo "Plain clone verify failed"; exit 1; }
$BOAR --repo=$CLONE co S || { echo "Plain clone checkout failed"; exit 1; }
(cd S && md5sum -c manifest.md5 ) || exit 1
rm -r S $REPO $CLONE || exit 1

exit 0
