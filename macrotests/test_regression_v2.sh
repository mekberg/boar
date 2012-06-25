# Test for regression issues with repo and workdir format from
# repository format version v2.

testdir="`pwd`"
tar -xzf $BOARTESTHOME/regression-v2.tar.gz || exit 1
REPO=$testdir/regression-v2/TESTREPO

cat >expected.txt <<EOF
NOTICE: Old repo format detected. Upgrading...
!Checking out to workdir .*/TestSession
modified.txt
windows-räksmörgås.txt
attention.png
!Finished in .* seconds
EOF

$BOAR --repo=$REPO co TestSession >output.txt 2>&1 || { cat output.txt; echo "Initial checkout failed"; exit 1; }
txtmatch.py expected.txt output.txt || { echo "Unexpected checkout output"; exit 1; }

cat >expected.txt <<EOF
[1, null, "TestSession", "d41d8cd98f00b204e9800998ecf8427e", null, false]
[2, 1, "TestSession", "e2c11232d43a33f0664681e0fb232061", null, false]
[3, null, "__deleted", "d41d8cd98f00b204e9800998ecf8427e", null, true]
[4, 2, "TestSession", "5791c15761a4e099e15b90265f28cd11", null, false]
!Finished in .* seconds
EOF

$BOAR --repo=$REPO list --dump >output.txt 2>&1 || { cat output.txt; echo "Repo dump failed"; exit 1; }
txtmatch.py expected.txt output.txt || { echo "Unexpected dump output"; exit 1; }

cat >expected.txt <<EOF
--------------------------------------------------------------------------------
!r4 \| TestSession \| .* \| 0 log lines
Changed paths:
M modified.txt

--------------------------------------------------------------------------------
!r2 \| TestSession \| .* \| 0 log lines
Changed paths:
A attention.png
A modified.txt
A windows-räksmörgås.txt

--------------------------------------------------------------------------------
!r1 \| TestSession \| .* \| 0 log lines
Changed paths:

--------------------------------------------------------------------------------
!Finished in .* seconds
EOF

$BOAR --repo=$REPO log -v >output.txt 2>&1 || { cat output.txt; echo "Repo log -v failed"; exit 1; }
txtmatch.py expected.txt output.txt || { echo "Unexpected log -v output"; exit 1; }


REPO_PATH=$REPO $BOAR verify || { echo "Couldn't verify"; exit 1; }
(cd TestSession && ls)
(cd TestSession && md5sum -c ../regression-v2/r4.md5) || exit 1

echo "--- Test repo cloning"
tar -xzf $BOARTESTHOME/regression-v2.tar.gz || exit 1
$BOAR clone $REPO clone || { echo "Couldn't clone"; exit 1; }

$BOARTESTHOME/excercise_repo.sh $BOAR $REPO || { echo "Excercise of v2 repo failed"; exit 1; }
