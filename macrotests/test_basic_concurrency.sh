# Test that several processes can work with the repository concurrently.

set -e
$BOAR mkrepo TESTREPO || exit 1

dotest()
{
    SESSION=$1
    $BOAR mksession --repo=TESTREPO $SESSION || exit 1
    $BOAR co --repo=TESTREPO $SESSION || exit 1
    for i in {1..10}; do
	echo "$SESSION PID=$$ commit ${i} here" >$SESSION/commit.txt || exit 1
	for j in {1..100}; do
	    date >$SESSION/"$i-$j.txt"
	done
	(cd $SESSION && $BOAR ci -q) || exit 1
    done

    # Now verify that all data is present
    REVS=$($BOAR list --repo=TESTREPO $SESSION|grep Revision|cut -d ' ' -f 3)
    index=0
    for rev in $REVS; do	
	if [ $index -ne 0 ]; then 
	    # The first revision is session creation and will not contain the file
	    (cd $SESSION && $BOAR update -q -r $rev) || exit 1
	    grep "commit $index here" $SESSION/commit.txt || { echo "Revision $rev did not contain expected data"; exit 1; }
	fi
	index=$[$index + 1]
    done

    if [ $index -ne 11 ]; then
	echo "Wrong number of revisions for $SESSION"
	exit 1
    fi
}

PIDS=""
for i in {0..5}; do
    dotest Session$i >Session$i.txt 2>&1 &
    PIDS="$PIDS $!"
done

for PID in $PIDS; do
    wait $PID || { echo "Process $PID failed"; exit 1; }
done

$BOAR verify --repo=TESTREPO || exit 1

true
