testdir="`pwd`"
tar -xzf $BOARTESTHOME/reciperepo.tar.gz || exit 1
REPO=$testdir/reciperepo

# Verify simple recipe repo NOTE: this repo does not contain a block
# db. Commits will not be correctly deduplicated.
$BOAR --repo=$REPO co Alice || { echo "Check-out failed"; exit 1; }
$BOAR --repo=$REPO verify || { echo "Verify failed"; exit 1; }
(cd Alice && md5sum -c || exit 1) <<EOF
9b97d0a697dc503fb4c53ea01bd23dc7  alice.txt
EOF
cp Alice/alice.txt . || exit 1
rm -r $REPO Alice || exit 1

#################

$BOAR mkrepo $REPO || exit 1
$BOAR --repo=$REPO mksession Dedup || exit 1
$BOAR --repo=$REPO co Dedup || exit 1
(cd Dedup && cp ../alice.txt . && $BOAR ci -q) || exit 1

(cd Dedup && 
    echo "SOME PREPENDED DATA" >prefix.txt && 
    echo "SOME APPENDED DATA" >suffix.txt && 
    cat prefix.txt alice.txt suffix.txt >amalgam.txt &&
    md5sum *.txt >manifest.md5 &&
    cat manifest.md5 &&
    $BOAR ci -q ) || exit 1

rm -r Dedup || exit 1

$BOAR --repo=$REPO co Dedup || { echo "Check-out 2 failed"; exit 1; }


ls $REPO/recipes
exit 1


