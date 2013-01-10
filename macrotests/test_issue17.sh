#!/bin/bash
# Test concurrent commits

TESTREPO="`pwd`/TESTREPO"
TESTDIR=`pwd`

$BOAR mkrepo $TESTREPO || exit 1
$BOAR --repo=$TESTREPO mksession "TestSession" || exit 1
$BOAR --repo=$TESTREPO co TestSession wd1 || exit 1
mkdir wd1/subdir || exit 1
echo "Content 1" >wd1/subdir/file.txt || exit 1
echo "Content 2" >wd1/deleted_file.txt || exit 1
(cd wd1 && $BOAR ci ) || exit 1

$BOAR --repo=$TESTREPO co TestSession/subdir wd2 || exit 1
$BOAR --repo=$TESTREPO co TestSession wd3 || exit 1

rm wd1/deleted_file.txt
(cd wd1 && $BOAR ci -q ) || exit 1

RESULT1=$TESTDIR/result1.txt
RESULT2=$TESTDIR/result2.txt

(cd wd2 && $BOAR update -q 2>&1 | tee $RESULT1 ) || exit 1

if ! grep "Workdir now at revision 3" $RESULT1; then
    echo "Test failed. Unexpected output."
    exit 1
fi

if grep "Deletion failed" $RESULT1; then
    echo "Test failed. Got 'deletion failed' message for file outside checked out tree"
    exit 1
fi

rm wd3/deleted_file.txt
(cd wd3 && $BOAR update -q 2>&1 | tee $RESULT2 ) || exit 1

if ! grep "Deletion failed" $RESULT2; then
    echo "Test failed. Did NOT get 'deletion failed' message for externally removed file."
    exit 1
fi
