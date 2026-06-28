# Tests for "boar clone --reflink". The clone shares blobs with the source
# via copy-on-write reflinks where the destination would store them
# verbatim, while destinations that deduplicate/split still do so.
#
# This test only runs on a reflink-capable filesystem (XFS, btrfs, ...).
# It is skipped otherwise. To exercise it, run the macro suite with its
# temporary directory on such a filesystem.

# Skip if reflinks are not supported here, or when running against remote
# repositories (reflink is local-only and rejected for remote repos).
if ! python3 -c "import sys, os, tempfile; sys.path.insert(0, '${BOARTESTHOME}/..'); import common; fd, p = tempfile.mkstemp(dir='.'); os.write(fd, b'x'); os.close(fd); r = common.reflink_supported(p, '.'); os.unlink(p); sys.exit(0 if r else 1)"; then
    echo "Skipping: filesystem does not support reflinks"
    exit 0
fi
if [ "$BOAR_TEST_REMOTE_REPO" == "1" ] || [ "$BOAR_TEST_REMOTE_REPO" == "2" ]; then
    # --reflink must be rejected for remote repositories.
    $BOAR mkrepo src >/dev/null || exit 1
    $BOAR --repo=src mksession S >/dev/null || exit 1
    $BOAR --repo=src co S wd >/dev/null || exit 1
    (cd wd && echo hello >a.txt && $BOAR ci -q) >/dev/null || exit 1
    if $BOAR clone --reflink src dst >err.txt 2>&1; then
        echo "FAIL: --reflink should have been rejected for remote repos"; exit 1
    fi
    grep -q "local repositories" err.txt || { echo "FAIL: wrong error for remote --reflink"; cat err.txt; exit 1; }
    echo "remote --reflink correctly rejected"
    exit 0
fi

TESTDIR="`pwd`"
BOARBIG=$TESTDIR/big.bin
python3 -c "import os; open('$BOARBIG','wb').write(os.urandom(8*1024*1024))"
BIGMD5=`md5sum $BOARBIG | cut -d' ' -f1`

############################################################
echo "*** Plain destination: blobs are reflinked"

$BOAR mkrepo src || exit 1
$BOAR --repo=src mksession S || exit 1
$BOAR --repo=src co S wd || exit 1
(cd wd && cp $BOARBIG a.bin && printf 'prefix' | cat - $BOARBIG >b.bin && md5sum a.bin b.bin >manifest.md5 && $BOAR ci -q) || exit 1

$BOAR clone --reflink src dst_plain | tee plain_clone.log || { echo "reflink clone failed"; exit 1; }
# Both blobs must be reflinked, none copied (a successful FICLONE shares the
# data copy-on-write). The count is deterministic, unlike a free-space delta
# on a shared filesystem.
grep -q "Reflinked [1-9][0-9]* blob(s); copied 0 blob(s)." plain_clone.log || {
    echo "FAIL: expected all blobs reflinked, none copied"; cat plain_clone.log; exit 1; }
# The big file must be a plain raw blob in the clone.
test -e dst_plain/blobs/${BIGMD5:0:2}/$BIGMD5 || { echo "FAIL: expected raw blob in clone"; exit 1; }
$BOAR --repo=dst_plain verify || { echo "FAIL: clone verify"; exit 1; }
$BOAR --repo=dst_plain co S co_check || exit 1
(cd co_check && md5sum -c manifest.md5) || exit 1

############################################################
echo "*** Deduplicating destination still deduplicates (not reflinked)"

if [ "$BOAR_SKIP_DEDUP_TESTS" != "1" ]; then
    $BOAR mkrepo --enable-deduplication dst_dedup || exit 1
    $BOAR clone --reflink src dst_dedup | tee dedup_clone.log || { echo "reflink clone to dedup repo failed"; exit 1; }
    # b.bin is a near-duplicate of a.bin, so it must become a recipe...
    BMD5=`md5sum wd/b.bin | cut -d' ' -f1`
    test -e dst_dedup/recipes/${BMD5:0:2}/$BMD5.recipe || { echo "FAIL: dedup did not run in reflink clone"; exit 1; }
    # ...while a.bin has no duplicate blocks, so it is stored raw AND reflinked.
    test -e dst_dedup/blobs/${BIGMD5:0:2}/$BIGMD5 || { echo "FAIL: verbatim blob not stored raw"; exit 1; }
    grep -q "Reflinked [1-9]" dedup_clone.log || { echo "FAIL: no blobs reflinked into dedup repo"; cat dedup_clone.log; exit 1; }
    $BOAR --repo=dst_dedup verify || { echo "FAIL: dedup clone verify"; exit 1; }
fi

echo "All reflink tests passed"
exit 0
