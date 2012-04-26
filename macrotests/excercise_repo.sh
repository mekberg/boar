BOAR=$1
REPO=$2
CLONE=`mktemp -u EXCERCISE_CLONE_XXXX`

prefix="Repo excerciser:"
REPO_PATH=$REPO $BOAR verify || { echo $prefix "Verify failed"; exit 1; }
REPO_PATH=$REPO $BOAR ls || { echo $prefix "Ls failed"; exit 1; }
REPO_PATH=$REPO $BOAR list -m || { echo $prefix "List -m failed"; exit 1; }
REPO_PATH=$REPO $BOAR list --dump || { echo $prefix "List --dump failed"; exit 1; }

SESSIONS=$(REPO_PATH=$REPO $BOAR ls |grep -v Finished| sed -e 's/ (.*)$//g')
for session in $SESSIONS; do
    # Simple checkout of latest revision
    CO_NAME=`mktemp -u EXCERCISE_CO_XXXX`
    REPO_PATH=$REPO $BOAR co $session "$CO_NAME" || { echo $prefix "Co of session '$session' failed"; exit 1; }
    rm -r "$CO_NAME" || exit 1

    # Check out every revision of this session explicitly
    REVISIONS=$($BOAR --repo=$REPO list $session |grep "Revision id"|cut -d ' ' -f 3)
    for revision in $REVISIONS; do
	CO_NAME=`mktemp -u EXCERCISE_CO_XXXX`
	REPO_PATH=$REPO $BOAR co -r $revision $session "$CO_NAME" || { 
	    echo $prefix "Co of session '$session' revision $revision failed"; exit 1; }
	rm -r "$CO_NAME" || exit 1    
    done
done
exit 1

$BOAR clone $REPO $CLONE || { echo $prefix "Clone failed (Clone path: $CLONE)"; exit 1; }
$BOAR verify --repo=$CLONE || { echo $prefix "Clone verify failed (Clone path: $CLONE)"; exit 1; }
rm -r $CLONE || { echo $prefix "Couldn't remove clone (Clone path: $CLONE)"; exit 1; }
