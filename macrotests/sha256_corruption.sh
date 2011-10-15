# Test option to ignore errors during import

BOAR=~+/`dirname $0`/../boar
testdir="/tmp/sha256_corruption_tmp$$"
mkdir $testdir || exit 1
cd $testdir || exit 1

$BOAR mkrepo TESTREPO || exit 1
REPO=`pwd`/TESTREPO
REPO_PATH=$REPO $BOAR mksession Sha256Test || { echo "Couldn't create Sha256Test session"; exit 1; }
mkdir test_tree || { echo "Couldn't create test_tree dir for sha256"; exit 1; }
echo "Some content" >test_tree/file1.txt || exit 1
REPO_PATH=$REPO $BOAR import -w -v test_tree Sha256Test || { echo "Couldn't import tree"; exit 1; }
echo "Some content" >test_tree/file2.txt || exit 1
(cd test_tree && REPO_PATH=$REPO $BOAR ci) || { echo "Couldn't ci Sha256Test session"; exit 1; }

echo "-- Testing mangled db file"
echo "Some content" >test_tree/file3.txt || exit 1
echo "Obvious Corruption" >$REPO/derived/sha256/sha256cache || exit 1
(cd test_tree && REPO_PATH=$REPO $BOAR ci)
if [ "$?" -ne 7 ]; then 
    echo "Did not get expected error code"; 
    exit 1; 
fi
REPO_PATH=$REPO $BOAR verify && { echo "Verify didn't detect error"; exit 1; }
REPO_PATH=$REPO $BOAR repair || { echo "Repair failed"; exit 1; }
REPO_PATH=$REPO $BOAR verify || { echo "Verify failed after repair"; exit 1; }

echo "-- Testing that cache has regenerated ok"
sqlite3 $REPO/derived/sha256/sha256cache "SELECT * FROM CHECKSUMS" >content.txt
diff content.txt - <<EOF || { echo "Db did not contain blob checksum after verify"; exit 1; }
581ab2d89f05c294d4fe69c623bdef83|e1ed54b5c51c88d44304d1910a335863d66354f2a3bf2770c9ee977c391eed2a|50614d8875159a5e3137daf159352733
EOF

echo "-- Testing healthy repo repair"
REPO_PATH=$REPO $BOAR verify || { echo "Repo should not be broken here"; exit 1; }
REPO_PATH=$REPO $BOAR repair || { echo "Repair failed"; exit 1; }
REPO_PATH=$REPO $BOAR verify || { echo "Verify failed after repair"; exit 1; }

echo "-- Testing row level corruption"
sqlite3 $REPO/derived/sha256/sha256cache "UPDATE CHECKSUMS SET sha256 = '0000000000000000000000000000000000000000000000000000000000000000'"
REPO_PATH=$REPO $BOAR verify && { echo "Verify didn't detect error"; exit 1; }
REPO_PATH=$REPO $BOAR repair || { echo "Repair failed"; exit 1; }
REPO_PATH=$REPO $BOAR verify || { echo "Verify failed after repair"; exit 1; }

echo "-- Testing row level corruption with correct row checksum"
sqlite3 $REPO/derived/sha256/sha256cache "UPDATE CHECKSUMS SET sha256 = '0000000000000000000000000000000000000000000000000000000000000000', row_md5 = '3421c9a8397f59ec191d1c10ca73a930'"
REPO_PATH=$REPO $BOAR verify && { echo "Verify didn't detect error"; exit 1; }
REPO_PATH=$REPO $BOAR repair || { echo "Repair failed"; exit 1; }
REPO_PATH=$REPO $BOAR verify || { echo "Verify failed after repair"; exit 1; }

rm -r $testdir