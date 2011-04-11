#!/bin/bash

# Test concurrent commits

testname="issue17"
boar="`pwd`/../boar"
testdir="/tmp/${testname}_tmp$$"
TESTREPO="${testdir}/${testname}_TESTREPO"
mkdir $testdir || exit 1

$boar mkrepo $TESTREPO || exit 1
$boar --repo=$TESTREPO mksession "TestSession" || exit 1
$boar --repo=$TESTREPO co TestSession $testdir/wd1 || exit 1
mkdir $testdir/wd1/subdir || exit 1
echo "Content 1" >$testdir/wd1/subdir/file.txt || exit 1
echo "Content 2" >$testdir/wd1/deleted_file.txt || exit 1
(cd $testdir/wd1 && $boar ci ) || exit 1

$boar --repo=$TESTREPO co TestSession/subdir $testdir/wd2 || exit 1
$boar --repo=$TESTREPO co TestSession $testdir/wd3 || exit 1

rm $testdir/wd1/deleted_file.txt
(cd $testdir/wd1 && $boar ci ) || exit 1

(cd $testdir/wd2 && $boar update 2>&1 | tee $testdir/result1.txt ) || exit 1
if grep "Deletion failed" $testdir/result1.txt; then
    echo "Test failed. Got 'deletion failed' message for file outside checked out tree"
    exit 1
fi

rm $testdir/wd3/deleted_file.txt
(cd $testdir/wd3 && $boar update 2>&1 | tee $testdir/result2.txt ) || exit 1
if ! grep "Deletion failed" $testdir/result2.txt; then
    echo "Test failed. Did NOT get 'deletion failed' message for externally removed file."
    exit 1
fi

rm -r $testdir
echo "Test $testname successful"
