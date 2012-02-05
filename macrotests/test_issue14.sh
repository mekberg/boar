#!/bin/bash

# Test concurrent commits

testname="issue14"
TESTREPO="`pwd`/TESTREPO"

$BOAR mkrepo $TESTREPO || exit 1
$BOAR --repo=$TESTREPO mksession "TestSession" || exit 1
$BOAR --repo=$TESTREPO co TestSession wd1 || exit 1
$BOAR --repo=$TESTREPO co TestSession wd2 || exit 1

dd if=/dev/urandom of=wd1/bigfile.txt bs=1024 count=1024 || exit 1
echo "Some data" >wd2/afile.txt
sync
cd wd1 
$BOAR ci &
pid=$!

# We do not want to rely on just timing here... We'll let the first
# commit start, then pause that process until the second commit is
# finished.  We will achieve this by waiting until there is something
# in the tmp dir, that should indicate that the commit has commenced.

# This is not very pretty... TODO: make pretty

while [ "`ls $TESTREPO/tmp/`" == "" ]; do
    # wait for session to be created
    true
done
while [ "`ls $TESTREPO/tmp/*/`" == "" ]; do
    # wait for blob data to start dropping in
    true
done

kill -SIGTSTP $pid

if [ "`ls $TESTREPO/tmp`" == "" ]; then
    echo "Stop didn't stop in time"
    exit 1
fi

echo "First commit is in progress and has been paused."
echo "Performing second commit (should fail)"
( cd wd2 && $BOAR ci ) && { echo "*** Test failed. Concurrent checkin succeeded, should fail." ; exit 1; }
echo "Second commit done"
echo "Resuming first commit"
kill -SIGCONT $pid
wait $pid || { echo "*** Test failed. First commit failed. Should succeed." ; exit 1; }


