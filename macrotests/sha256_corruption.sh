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
echo "Some content" >test_tree/file3.txt || exit 1
echo "Corruption" >$REPO/derived/sha256/sha256cache || exit 1
(cd test_tree && REPO_PATH=$REPO $BOAR ci)
if [ "$?" -ne 7 ]; then 
    echo "Did not get expected error code"; 
    exit 1; 
fi
echo Executing verify
REPO_PATH=$REPO $BOAR verify && { echo "Verify didn't detect error"; exit 1; }
REPO_PATH=$REPO $BOAR repair || { echo "Repair failed"; exit 1; }
REPO_PATH=$REPO $BOAR verify || { echo "Verify failed after repair"; exit 1; }
rm -r $testdir