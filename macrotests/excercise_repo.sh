BOAR=$1
REPO=$2
CLONE=`mktemp -u EXCERCISE_CLONE_XXXX`

prefix="Repo excerciser:"
REPO_PATH=$REPO $BOAR verify || { echo $prefix "Verify failed"; exit 1; }
REPO_PATH=$REPO $BOAR ls || { echo $prefix "Ls failed"; exit 1; }
REPO_PATH=$REPO $BOAR list -m || { echo $prefix "List -m failed"; exit 1; }
REPO_PATH=$REPO $BOAR list --dump || { echo $prefix "List --dump failed"; exit 1; }
$BOAR clone $REPO $CLONE || { echo $prefix "Clone failed (Clone path: $CLONE)"; exit 1; }
$BOAR verify --repo=$CLONE || { echo $prefix "Clone verify failed (Clone path: $CLONE)"; exit 1; }
rm -r $CLONE || { echo $prefix "Couldn't remove clone (Clone path: $CLONE)"; exit 1; }
