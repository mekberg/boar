#!/bin/bash

fail()
{
    echo -n "Failure at line "; 
    caller
    exit 1; 
}

VMCMD=`pwd`/verify-manifests.py
TESTDIR=`mktemp -d`
REPO="$TESTDIR/TESTREPO"
REALBOAR=`which boar`

export PATH="$TESTDIR:$PATH"

echo "Test directory is $TESTDIR"

cd $TESTDIR

$VMCMD --help || { echo "Simple --help failed"; fail; }

mkdir Tree || fail

echo "Avocado" > Tree/a.txt || fail
echo "Avocado2" > Tree/räksmörgås.txt || fail
echo "Avocado3" > Tree/b.txt || fail

cat >Tree/manifest-a1f3dd91c814f423c6d67a96a38818e1.md5 <<EOF
687a94ea5dad1fa7076956b3e4b0b981  a.txt
0a2c35b169df33ba62d637736ed4781a  räksmörgås.txt
EOF

cat >Tree/manifest.md5 <<EOF
0a2c35b169df33ba62d637736ed4781a  räksmörgås.txt
0416cb373a61b43e297071e571730436  b.txt
EOF

boar mkrepo $REPO || { echo "Boar mkrepo failed"; fail; }
boar --repo=$REPO mksession Stuff || fail
boar --repo=$REPO import Tree Stuff || fail

####################################################
# Test happy path                                  #
####################################################
$VMCMD $REPO -B a1f3dd91c814f423c6d67a96a38818e1 || { 
    echo "Verifying manifest by blobid failed"; fail; }
$VMCMD $REPO -S Stuff/manifest-a1f3dd91c814f423c6d67a96a38818e1.md5 Stuff/manifest.md5 || { 
    echo "Verifying manifest by session path failed"; fail; }
$VMCMD $REPO -F "$TESTDIR/Tree/manifest-a1f3dd91c814f423c6d67a96a38818e1.md5" || { 
    echo "Verifying manifest by file path failed"; fail; }

echo a1f3dd91c814f423c6d67a96a38818e1 | $VMCMD $REPO -B --stdin || { 
    echo "Verifying manifest by stdin blobid failed"; fail; }
echo Stuff/manifest-a1f3dd91c814f423c6d67a96a38818e1.md5 | $VMCMD $REPO -S --stdin || { 
    echo "Verifying manifest by stdin session path failed"; fail; }
echo "$TESTDIR/Tree/manifest-a1f3dd91c814f423c6d67a96a38818e1.md5" | $VMCMD $REPO -F --stdin || { 
    echo "Verifying manifest by stdin file path failed"; fail; }

########################################################################
# Test detection of corrupt (but valid) manifest caused by bug in boar #
########################################################################

# This is a fake "boar" that returns corrupted data when cat:ing the
# manifest. Note that the data is valid, just missing an entry.
cat >boar <<EOF
#!/bin/bash
if [[ "\$@" == *a1f3dd91c814f423c6d67a96a38818e1* ]]; then
  echo "687a94ea5dad1fa7076956b3e4b0b981  a.txt"
else
  $REALBOAR \$@
fi
EOF
chmod a+x boar || fail

# This manifest should fail
$VMCMD $REPO -S Stuff/manifest-a1f3dd91c814f423c6d67a96a38818e1.md5 >output.txt && { 
    echo "Verifying corrupt manifest should fail"; fail; }

grep "Manifest checksum didn't match contents" output.txt || fail
grep "ERROR WHILE VERIFYING MANIFEST Stuff/manifest-a1f3dd91c814f423c6d67a96a38818e1.md5" output.txt || fail
rm output.txt || fail

# This manifest should fail
echo "687a94ea5dad1fa7076956b3e4b0b981  a.txt" >broken-manifest-a1f3dd91c814f423c6d67a96a38818e1.md5 || fail
$VMCMD $REPO -F broken-manifest-a1f3dd91c814f423c6d67a96a38818e1.md5 >output.txt && { 
    echo "Verifying corrupt manifest should fail"; fail; }
grep "Manifest checksum didn't match contents" output.txt || fail
grep "ERROR WHILE VERIFYING MANIFEST broken-manifest-a1f3dd91c814f423c6d67a96a38818e1.md5" output.txt || fail
rm broken-manifest-a1f3dd91c814f423c6d67a96a38818e1.md5 output.txt || fail

# This manifest should fail. When accessing the manifest by checksum,
# BoarExt will discover that the blob is corrupt, we'll never get a
# chance to explicitly verify the manifest checksum - but that's ok.
$VMCMD $REPO -B a1f3dd91c814f423c6d67a96a38818e1 >output.txt && { 
    echo "Verifying corrupt manifest should fail"; fail; }
grep "Invalid checksum for blob: a1f3dd91c814f423c6d67a96a38818e1" output.txt || fail
grep "ERROR WHILE VERIFYING MANIFEST a1f3dd91c814f423c6d67a96a38818e1" output.txt || fail
rm output.txt boar || fail

########################################################
# Test detection of corrupt blob caused by bug in boar #
########################################################

# This is a fake "boar" that returns corrupted data when cat:ing blob
# 687a94ea5dad1fa7076956b3e4b0b981 but otherwise works as usual.
cat >boar <<EOF
#!/bin/bash
if [[ "\$@" == *687a94ea5dad1fa7076956b3e4b0b981* ]]; then
  echo "Not the expected data"
else
  $REALBOAR \$@
fi
EOF
chmod a+x boar || fail

# This manifest should still work - does not contain the broken blob
$VMCMD $REPO -S Stuff/manifest.md5 || { 
    echo "Verifying working manifest should work"; fail; }

# This manifest should fail
$VMCMD $REPO -B a1f3dd91c814f423c6d67a96a38818e1 >output.txt && { 
    echo "Verifying broken manifest by session path should fail"; fail; }

grep "Invalid checksum for blob: 687a94ea5dad1fa7076956b3e4b0b981" output.txt || fail

rm output.txt boar || fail

####################################################
# Test detection of missing blob                   #
####################################################

boar --repo=$REPO co Stuff || fail
rm Stuff/a.txt || fail
mv Stuff/manifest-a1f3dd91c814f423c6d67a96a38818e1.md5 Stuff/not-a-manifest.txt || fail
(cd Stuff ; boar ci -m"Removed manifest and a file") || fail
touch $REPO/ENABLE_PERMANENT_ERASE || fail
boar --repo=$REPO truncate Stuff || fail

check_missing_blob_output()
{
    grep "Blob 687a94ea5dad1fa7076956b3e4b0b981 is missing" output.txt && rm output.txt
}

$VMCMD $REPO -B a1f3dd91c814f423c6d67a96a38818e1 > output.txt && { 
    echo "Verifying broken manifest by blobid should fail"; fail; }
check_missing_blob_output || fail
$VMCMD $REPO -S Stuff/not-a-manifest.txt > output.txt && { 
    echo "Verifying broken manifest by session path should fail"; fail; }
check_missing_blob_output || fail
$VMCMD $REPO -F "$TESTDIR/Tree/manifest-a1f3dd91c814f423c6d67a96a38818e1.md5" > output.txt && { 
    echo "Verifying broken manifest by file path should fail failed"; fail; }
check_missing_blob_output || fail

echo a1f3dd91c814f423c6d67a96a38818e1 | $VMCMD $REPO -B --stdin > output.txt && { 
    echo "Verifying broken manifest by stdin blobid should fail"; fail; }
check_missing_blob_output || fail
# Test working manifest before and after the broken one
echo -e "Stuff/manifest.md5\nStuff/not-a-manifest.txt\nStuff/manifest.md5" | $VMCMD $REPO -S --stdin > output.txt && { 
    echo "Verifying broken manifest by stdin session path should fail"; fail; }
check_missing_blob_output || fail
# Test broken manifest before and after a working one
echo -e "Stuff/not-a-manifest.txt\nStuff/manifest.md5\nStuff/not-a-manifest.txt\n" | $VMCMD $REPO -S --stdin > output.txt && { 
    echo "Verifying broken manifest by stdin session path should fail"; fail; }
check_missing_blob_output || fail
echo "$TESTDIR/Tree/manifest-a1f3dd91c814f423c6d67a96a38818e1.md5" | $VMCMD $REPO -F --stdin > output.txt && { 
    echo "Verifying broken manifest by stdin file path should fail"; fail; }
check_missing_blob_output || fail



echo "ALL OK"
rm -r $TESTDIR