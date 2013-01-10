set -e
$BOAR mkrepo TESTREPO || exit 1
$BOAR --repo=TESTREPO mksession "Session1" || exit 1
$BOAR --repo=TESTREPO mksession "Session2" || exit 1
$BOAR --repo=TESTREPO co "Session1" || exit 1
$BOAR --repo=TESTREPO co "Session2" || exit 1

echo "Some identical content" >data.txt || exit 1
cp data.txt Session1/data1.txt || exit 1
cp data.txt Session2/data2.txt || exit 1

# Test for file that is readable during changes scan, but unreadable during actual checkin
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

cd Session1 || exit 1
$BOAR --EXEC ../pause_at_commit.py ci -q &
cd .. || exit 1

sleep 1
while ! test -e pid.txt; do
    echo "No pid.txt yet..."
    sleep 1
done

if [ "`ls TESTREPO/tmp`" == "" ]; then
    echo "Stop didn't stop in time"
    exit 1
fi

pid=`cat pid.txt`
( cd Session2 && $BOAR ci -q ) || { echo "Concurrent commit on different session should succeed"; exit 1; }

kill -SIGCONT $pid

wait $pid || { echo "First commit failed"; exit 1; }

true
