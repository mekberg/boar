#!/bin/bash

# Test concurrent commits

# The idea of this test is to see what happens when another commit is
# made while an earlier commit is still in progress. We do this by
# starting one commit, pause the process while it is in the middle of
# things, then try to make another commit. The expected behaviour is
# that only the commit started first will succeed.

testname="issue14"
TESTREPO="`pwd`/TESTREPO"

$BOAR mkrepo $TESTREPO || exit 1
$BOAR --repo=$TESTREPO mksession "TestSession" || exit 1
$BOAR --repo=$TESTREPO co TestSession wd1 || exit 1
$BOAR --repo=$TESTREPO co TestSession wd2 || exit 1


cat >pause_at_commit.py <<"EOF"
def modify_fn(fn):
    def newfn(*args, **kwargs):
        """ When a file is committed, pause the process and write 
            the pid to pid.txt. Then restore the original function 
            to make sure this only happens once."""
        import os, signal
        open("../pid.txt", "w").write(str(os.getpid()))
	fn(*args, **kwargs)
	os.kill(os.getpid(), signal.SIGSTOP)
        workdir.check_in_file = fn
    return newfn

workdir.check_in_file = modify_fn(workdir.check_in_file)
EOF

echo "A little bit of data" >wd1/wd1file.txt || exit 1
echo "Some more data" >wd2/wd2file.txt || exit 1

cd wd1 || exit 1
$BOAR --EXEC ../pause_at_commit.py ci -q &
cd .. || exit 1

sleep 1

while ! test -e pid.txt; do
    echo "No pid.txt yet..."
    sleep 1
done

pid=`cat pid.txt`
echo "Paused with pid $pid"

if [ "`ls $TESTREPO/tmp`" == "" ]; then
    echo "Stop didn't stop in time"
    exit 1
fi

echo "First commit is in progress and has been paused."
echo "Performing second commit (should fail)"
( cd wd2 && $BOAR ci -q ) && { echo "*** Test failed. Concurrent checkin succeeded, should fail." ; exit 1; }
echo "Second commit done"
echo "Resuming first commit"
kill -SIGCONT $pid
wait $pid || { echo "*** Test failed. First commit failed. Should succeed." ; exit 1; }
