TESTDIR="`pwd`"
REPO=$TESTDIR/DEDUPREPO

$BOAR mkrepo $REPO || exit 1
$BOAR --repo=$REPO mksession Session || exit 1
mkdir Tree || exit 1
touch Tree/tjosan
touch Tree/räksmörgås
python -c "open('Tree/illegal\xa0\xa1', 'w')" || exit 1
#python -c "import os; print os.listdir(u'Tree')" || exit 1

$BOAR import --repo=$REPO Tree Session >output.txt 2>&1 && { echo "Import should fail"; exit 1; }

# Cannot use txtmatch here, it gets confused by the illegal file name
grep "Found a filename that is illegal under the current file system encoding (UTF-8):" output.txt || { echo "Unexpected output:"; cat output.txt; exit 1; }

