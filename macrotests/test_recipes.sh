testdir="`pwd`"
tar -xzf $BOARTESTHOME/reciperepo.tar.gz || exit 1
REPO=$testdir/reciperepo

$BOAR --repo=$REPO co Alice || { echo "Check-out failed"; exit 1; }

$BOAR --repo=$REPO verify || { echo "Verify failed"; exit 1; }

