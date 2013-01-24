TESTDIR="`pwd`"
tar -xzf $BOARTESTHOME/reciperepo.tar.gz || exit 1
REPO=$TESTDIR/reciperepo
BIGFILE=$TESTDIR/bigfile.bin
mkrandfile.py 0 100000 $BIGFILE || exit 1
md5sum -c <<EOF || exit 1
028a14413856fee90edd49ad9f8af9c4  $BIGFILE
EOF

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

echo "Testing case of B followed by ABC"

$BOAR mkrepo $REPO || exit 1
$BOAR --repo=$REPO mksession Dedup || exit 1
$BOAR --repo=$REPO co Dedup || exit 1
(cd Dedup && cp $BIGFILE bigfile.bin && $BOAR ci -q) || exit 1 # Data blob B

(cd Dedup && 
    echo "SOME PREPENDED DATA" >prefix.txt && # Data blob A
    echo "SOME APPENDED DATA" >suffix.txt &&  # Data blob C
    cat prefix.txt bigfile.bin suffix.txt >amalgam.bin && # Data blob ABC
    md5sum *.bin *.txt >manifest.md5 &&
    cat manifest.md5 &&
    $BOAR ci -q ) || exit 1

rm -r Dedup || exit 1

$BOAR --repo=$REPO verify || { echo "Verify 2 failed"; exit 1; }
$BOAR --repo=$REPO co Dedup || { echo "Check-out 2 failed"; exit 1; }
(cd Dedup && md5sum -c manifest.md5 ) || exit 1
rm -r $REPO Dedup || exit 1

#################

echo "Testing case of ABC followed by B"
$BOAR mkrepo $REPO || exit 1
$BOAR --repo=$REPO mksession Dedup || exit 1
$BOAR --repo=$REPO co Dedup || exit 1

(cd Dedup && 
    echo "SOME PREPENDED DATA" >prefix.txt && # Data blob A
    echo "SOME APPENDED DATA" >suffix.txt &&  # Data blob C
    cat prefix.txt $BIGFILE suffix.txt >amalgam.bin && # Data blob ABC
    $BOAR ci -q ) || exit 1

(cd Dedup && 
    cp $BIGFILE bigfile.bin && # Data blob B
    md5sum *.bin *.txt >manifest.md5 && 
    $BOAR ci -q ) || exit 1

ls $REPO/recipes || exit 1
cat $REPO/recipes/028a14413856fee90edd49ad9f8af9c4.recipe || exit 1
rm -r Dedup || exit 1
exit 1

$BOAR --repo=$REPO verify || { echo "Verify failed"; exit 1; }
$BOAR --repo=$REPO co Dedup || { echo "Check-out failed"; exit 1; }
(cd Dedup && md5sum -c manifest.md5 ) || exit 1
rm -r $REPO Dedup || exit 1

exit 0
