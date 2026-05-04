#
# Issue 88: File mtimes should be restored on checkout/update.
#
# Verify that the mtime captured at commit time is reapplied to the
# file when it is later checked out or updated, and that the
# behaviour can be disabled with --no-restore-mtime.
#

set -e

export REPO_PATH=`pwd`/TESTREPO
$BOAR mkrepo $REPO_PATH
$BOAR mksession TestMtime

# Pin known mtimes that are clearly different from "now". Using two
# distinct historical timestamps lets us tell which revision a file
# came from after a checkout or update.
TS1="2015-06-02 12:01:06"
TS2="2020-01-15 03:14:07"

mkdir src1
echo "first contents" >src1/foo.txt
echo "first contents of bar" >src1/bar.txt
touch -d "$TS1" src1/foo.txt src1/bar.txt
EXPECTED1=`stat -c '%Y' src1/foo.txt`

$BOAR import -Wq src1 TestMtime

# --- Checkout (default: restore mtime) ---
$BOAR co TestMtime co_default >/dev/null
GOT=`stat -c '%Y' co_default/foo.txt`
test "$GOT" = "$EXPECTED1" || {
    echo "Checkout did not restore mtime (expected $EXPECTED1, got $GOT)"; exit 1; }

# --- Checkout with --no-restore-mtime ---
$BOAR co --no-restore-mtime TestMtime co_norestore >/dev/null
GOT=`stat -c '%Y' co_norestore/foo.txt`
test "$GOT" = "$EXPECTED1" && {
    echo "--no-restore-mtime should not have restored mtime"; exit 1; }

# Modifying a restored file should still be detected as a real
# modification (i.e. the workdir checksum cache must remain coherent
# after we adjust the mtime).
echo "modified locally" >co_default/foo.txt
(cd co_default && $BOAR status) | grep -E "^M foo.txt" || {
    echo "Modification of restored file was not detected"; exit 1; }
# Restore the file so the rest of the test starts from a clean state.
echo "first contents" >co_default/foo.txt
touch -d "$TS1" co_default/foo.txt

# --- Commit a new revision with a different historical mtime, then update ---
$BOAR co TestMtime workdir2 >/dev/null
echo "second contents" >workdir2/foo.txt
touch -d "$TS2" workdir2/foo.txt
EXPECTED2=`stat -c '%Y' workdir2/foo.txt`
(cd workdir2 && $BOAR ci -q)

# Default update should restore mtime.
(cd co_default && $BOAR update) >/dev/null
GOT=`stat -c '%Y' co_default/foo.txt`
test "$GOT" = "$EXPECTED2" || {
    echo "Update did not restore mtime (expected $EXPECTED2, got $GOT)"; exit 1; }

# --no-restore-mtime should leave the file with a recent mtime.
(cd co_norestore && $BOAR update --no-restore-mtime) >/dev/null
GOT=`stat -c '%Y' co_norestore/foo.txt`
test "$GOT" = "$EXPECTED2" && {
    echo "Update --no-restore-mtime should not have restored mtime"; exit 1; }

# After mtime restore, no spurious modifications should be reported.
(cd co_default && $BOAR status -q) >st.txt 2>&1
grep -E "^[MAD?] " st.txt && {
    cat st.txt; echo "Workdir reported spurious changes after update"; exit 1; }

# Symlink mode should silently skip mtime restoration (would otherwise
# mutate the shared blob in the repo). The link target's mtime is the
# blob's mtime, which is the time it was written to the repo, not the
# original file mtime. Symlink mode requires direct access to repo
# internals (front.repo.has_raw_blob / get_blob_path) which are not
# exposed over RPC, so skip this part under simulated remote.
if [ -z "$BOAR_TEST_REMOTE_REPO" ] || [ "$BOAR_TEST_REMOTE_REPO" = "0" ]; then
    $BOAR co -l TestMtime co_symlink >/dev/null
    test -L co_symlink/foo.txt || {
        echo "Expected symlink"; exit 1; }
    # Verify the symlink points at a repo blob (blob path contains "/blobs/").
    readlink co_symlink/foo.txt | grep -q "/blobs/" || {
        echo "Symlink does not point to repo blob"; exit 1; }
fi

exit 0
