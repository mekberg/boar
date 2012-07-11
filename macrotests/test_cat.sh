# Test that the cat command behaves as expected.

export REPO_PATH=`pwd`/TESTREPO
$BOAR mkrepo $REPO_PATH || exit 1
$BOAR mksession --repo=$REPO_PATH RäksmörgåsSession || exit 1
$BOAR co RäksmörgåsSession || exit 1

echo "Rev 2" >RäksmörgåsSession/r2.txt || exit 1
echo "Modified rev 2" >RäksmörgåsSession/modified.txt || exit 1
(cd RäksmörgåsSession && $BOAR ci -q) || exit 1

rm RäksmörgåsSession/r2.txt || exit 1
echo "Rev 3" >RäksmörgåsSession/r3.txt || exit 1
echo "Modified rev 3" >RäksmörgåsSession/modified.txt || exit 1
cp /bin/ls RäksmörgåsSession/räksmörgås.bin || exit 1
(cd RäksmörgåsSession && md5sum räksmörgås.bin >manifest-md5.txt) || exit 1
(cd RäksmörgåsSession && $BOAR ci -q) || exit 1

($BOAR cat RäksmörgåsSession/r3.txt | grep "Rev 3") || { echo "Unexpected output for cat r3.txt"; exit 1; }
$BOAR cat RäksmörgåsSession/r2.txt && { echo "Missing file should fail"; exit 1; }
$BOAR cat -r2 RäksmörgåsSession/r2.txt | grep "Rev 2" || { echo "Unexpected output for cat -r2 r2.txt"; exit 1; }
$BOAR cat RäksmörgåsSession/räksmörgås.bin >räksmörgås.bin || { echo "Binary file cat failed"; exit 1; }
md5sum -c RäksmörgåsSession/manifest-md5.txt || exit 1

cat >expected.txt <<EOF
Rev 3
Modified rev 3
EOF

$BOAR cat RäksmörgåsSession/r3.txt RäksmörgåsSession/modified.txt >output.txt || { 
    cat output.txt; echo "Couldn't cat multiple files"; exit 1; }
txtmatch.py expected.txt output.txt || { echo "Cat multiple files gave unexpected output"; exit 1; }

cat >expected.txt <<EOF
Modified rev 3
Rev 3
EOF
$BOAR cat -B ffa4cb9336e7655d1360220801edd01c 4b5c8990f5e8836e8f69bf5b1f19da9e >output.txt || {
    cat output.txt; echo "Couldn't cat multiple blobs"; exit 1; }
txtmatch.py expected.txt output.txt || { echo "Cat multiple blobs gave unexpected output"; exit 1; }

echo "All is well"
true
