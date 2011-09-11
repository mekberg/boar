# Test for regression issues with repo and workdir format from
# boar-daily.11-Jul-2011 (repository format version v0).

TESTHOME=~+/`dirname $0`
BOAR=$TESTHOME/../boar
testdir="/tmp/repo-regression$$"
mkdir $testdir || exit 1
cd $testdir || exit 1
tar xzf $TESTHOME/regression-boar-daily.11-Jul-2011.tar.gz || exit 1
REPO=$testdir/regression-boar-daily.11-Jul-2011/TESTREPO
cd regression-boar-daily.11-Jul-2011/workdir

# Relocate the workdir pointer to the repo.
patch $testdir/regression-boar-daily.11-Jul-2011/workdir/.meta/info <<EOF || exit 1
5c5
<     "repo_path": "/tmp/TESTREPO"
---
>     "repo_path": "$REPO"
EOF

REPO_PATH=$REPO $BOAR status || { echo "Couldn't execute status"; exit 1; }
md5sum -c ../r6.md5
REPO_PATH=$REPO $BOAR update -r2 || { echo "Couldn't execute status"; exit 1; }
md5sum -c ../r2.md5
REPO_PATH=$REPO $BOAR update || { echo "Couldn't execute status"; exit 1; }
md5sum -c ../r6.md5
cp some_text.txt some_text2.txt
REPO_PATH=$REPO $BOAR ci || { echo "Couldn't execute ci"; exit 1; }
REPO_PATH=$REPO $BOAR verify || { echo "Couldn't verify"; exit 1; }

cd $testdir || exit 1
rm -r regression-boar-daily.11-Jul-2011 || exit 1
tar xzf $TESTHOME/regression-boar-daily.11-Jul-2011.tar.gz || exit 1
echo "0" >$REPO/version.txt
REPO_PATH=$REPO $BOAR verify || { echo "Couldn't verify"; exit 1; }

rm -r $testdir
