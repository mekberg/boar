if [ "$BOAR_SKIP_DEDUP_TESTS" == "1" ]; then
    echo "Skipping due to BOAR_SKIP_DEDUP_TESTS"
    exit 0
fi

TESTDIR="`pwd`"
REPO=$TESTDIR/reciperepo
BIGFILE=$TESTDIR/bigfile.bin
mkrandfile.py 0 1000000 $BIGFILE || exit 1
md5sum -c <<EOF || exit 1
d978f6138c52b8be4f07bbbf571cd450  $BIGFILE
EOF


mkrandfile.py 0 1000000 A || exit 1
mkrandfile.py 1 1000000 B || exit 1
mkrandfile.py 2 1000000 C || exit 1

############################

echo "*** Testing case of files with identical blocks"
$BOAR mkrepo --enable-deduplication $REPO || exit 1
$BOAR --repo=$REPO mksession Dedup || exit 1
$BOAR --repo=$REPO co Dedup || exit 1

(cd Dedup && 
    dd if=/dev/zero of=zero512.bin bs=1024 count=512 &&
    md5sum zero512.bin >manifest.md5 &&
    $BOAR ci -q ) || exit 1

(cd Dedup && 
    dd if=/dev/zero of=zero1024.bin bs=1024 count=1024 &&
    md5sum *.bin | tee manifest.md5 &&
    $BOAR ci -q ) || exit 1

rm -r Dedup || exit 1

#b6d81b360a5672d80c27430f39153e2c  zero1024.bin
#59071590099d21dd439896592338bf95  zero512.bin

test -e $REPO/recipes/b6/b6d81b360a5672d80c27430f39153e2c.recipe || exit 1
test -e $REPO/blobs/59/59071590099d21dd439896592338bf95 || exit 1

$BOAR --repo=$REPO verify || { echo "Verify failed"; exit 1; }
$BOAR --repo=$REPO co Dedup || { echo "Check-out failed"; exit 1; }
(cd Dedup && md5sum -c manifest.md5 ) || exit 1
rm -r $REPO Dedup || exit 1

#################

echo "*** Testing case of B followed by ABC"

$BOAR mkrepo --enable-deduplication $REPO || exit 1
$BOAR --repo=$REPO mksession Dedup || exit 1
$BOAR --repo=$REPO co Dedup || exit 1
(cd Dedup && cp $BIGFILE bigfile.bin && $BOAR ci -q) || exit 1 # Data blob B

(cd Dedup && 
    echo "SOME PREPENDED DATA" >prefix.txt && # Data blob A
    echo "SOME APPENDED DATA" >suffix.txt &&  # Data blob C
    cat prefix.txt bigfile.bin suffix.txt >amalgam.bin && # Data blob ABC
    md5sum *.bin *.txt >manifest.md5 &&
    ls -l *.bin *.txt &&
    cat manifest.md5 &&
    $BOAR ci -q ) || exit 1

test -e $REPO/recipes/e4/e4050f3033f8b378843afeeea0b2f0e4.recipe || exit 1
rm -r Dedup || exit 1
$BOAR --repo=$REPO verify || { echo "Verify 2 failed"; exit 1; }
$BOAR --repo=$REPO co Dedup || { echo "Check-out 2 failed"; exit 1; }
(cd Dedup && md5sum -c manifest.md5 ) || exit 1
rm -r $REPO Dedup || exit 1

#################

echo "*** Testing case of ABC followed by B"
$BOAR mkrepo --enable-deduplication $REPO || exit 1
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

test -e $REPO/recipes/d9/d978f6138c52b8be4f07bbbf571cd450.recipe || exit 1
rm -r Dedup || exit 1

$BOAR --repo=$REPO verify || { echo "Verify failed"; exit 1; }
$BOAR --repo=$REPO co Dedup || { echo "Check-out failed"; exit 1; }
(cd Dedup && md5sum -c manifest.md5 ) || exit 1
rm -r $REPO Dedup || exit 1

#################

echo "*** Testing case of A followed by ABC followed by C"

$BOAR mkrepo --enable-deduplication $REPO || exit 1
$BOAR --repo=$REPO mksession Dedup || exit 1
$BOAR --repo=$REPO co Dedup || exit 1

(cd Dedup && 
    cp ../A . &&
    $BOAR ci -q ) || exit 1

(cd Dedup && 
    cat ../A ../B ../C >ABC &&
    $BOAR ci -q ) || exit 1

(cd Dedup && 
    cp ../C C &&
    md5sum A ABC C >manifest.md5 && 
    $BOAR ci -q ) || exit 1

rm -r Dedup || exit 1

$BOAR --repo=$REPO verify || { echo "Verify failed"; exit 1; }
$BOAR --repo=$REPO co Dedup || { echo "Check-out failed"; exit 1; }
(cd Dedup && md5sum -c manifest.md5 ) || exit 1
rm -r $REPO Dedup || exit 1

#################

echo "*** Testing case of A followed by {AB, AB}"

$BOAR mkrepo --enable-deduplication $REPO || exit 1
$BOAR --repo=$REPO mksession Dedup || exit 1
$BOAR --repo=$REPO co Dedup || exit 1

(cd Dedup && 
    cp ../A . &&
    $BOAR ci -q ) || exit 1

(cd Dedup && 
    cat ../A ../B >AB_1 &&
    cat ../A ../B >AB_2 &&
    md5sum A AB_1 AB_2 >manifest.md5 &&
    $BOAR ci -q ) || exit 1

rm -r Dedup || exit 1

$BOAR --repo=$REPO verify || { echo "Verify failed"; exit 1; }
$BOAR --repo=$REPO co Dedup || { echo "Check-out failed"; exit 1; }
(cd Dedup && md5sum -c manifest.md5 ) || exit 1
rm -r $REPO Dedup || exit 1

#########################

echo "*** Testing case of A followed by A with minor change"
#
# This test is primarily to do a sanity check on the size of a simple recipe.
#
$BOAR mkrepo --enable-deduplication $REPO || exit 1
$BOAR --repo=$REPO mksession Dedup || exit 1
$BOAR --repo=$REPO co Dedup || exit 1
(cd Dedup && cat $BIGFILE $BIGFILE $BIGFILE $BIGFILE $BIGFILE >bigfile.bin && $BOAR ci -q) || exit 1 # Data blob A

(cd Dedup && 
    echo "Tjosan" >>bigfile.bin &&
    md5sum bigfile.bin >manifest.md5 &&
    cat manifest.md5 &&
    $BOAR ci -q ) || exit 1
RECIPE_PATH="$REPO/recipes/0a/0ae8ec99045123ab029be41125d3426a.recipe"
cat $RECIPE_PATH || exit 1
echo

recipe_size=$(stat -c%s "$RECIPE_PATH")
if test $recipe_size -gt 1000; then
    echo "Recipe $RECIPE_PATH is unexpectedly large: $recipe_size"
    exit 1
fi

rm -r Dedup || exit 1
$BOAR --repo=$REPO verify || { echo "Verify 2 failed"; exit 1; }
$BOAR --repo=$REPO co Dedup || { echo "Check-out 2 failed"; exit 1; }
(cd Dedup && md5sum -c manifest.md5 ) || exit 1
rm -r $REPO Dedup || exit 1

#################

# echo "*** Testing case of single checkin of AA (redundancy within a single file)"
# $BOAR mkrepo --enable-deduplication $REPO || exit 1
# $BOAR --repo=$REPO mksession Dedup || exit 1
# $BOAR --repo=$REPO co Dedup || exit 1

# (cd Dedup && 
#     cat $BIGFILE $BIGFILE >amalgam.bin && # Data blob AA
#     md5sum amalgam.bin >manifest.md5 &&
#     $BOAR ci -q ) || exit 1

# ls -l $REPO/recipes || exit 1
# ls -l $REPO/blobs/02/028a14413856fee90edd49ad9f8af9c4 || exit 1

# $BOAR --repo=$REPO verify || { echo "Verify failed"; exit 1; }
# $BOAR --repo=$REPO co Dedup || { echo "Check-out failed"; exit 1; }
# (cd Dedup && md5sum -c manifest.md5 ) || exit 1
# rm -r $REPO Dedup || exit 1

############################

exit 0
