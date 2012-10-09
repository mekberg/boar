# Test that the log command behaves as expected.
set -e

$BOAR mkrepo TESTREPO || exit 1
$BOAR mksession --repo=TESTREPO TestSession || exit 1
$BOAR --repo=TESTREPO co TestSession || exit 1
echo "contents1" >TestSession/modified.txt || exit 1
echo "contents2" >TestSession/deleted.txt || exit 1
(cd TestSession && $BOAR ci -q -m "Comment line 1
Comment line 2") || exit 1

$BOAR mksession --repo=TESTREPO AnotherTestSession || exit 1
$BOAR --repo=TESTREPO co AnotherTestSession || exit 1
echo "contents3" >AnotherTestSession/somedata.txt || exit 1
(cd AnotherTestSession && $BOAR ci -q -m"Single line comment") || exit 1

echo "changed contents" >TestSession/modified.txt || exit 1
echo "contents4" >TestSession/new.txt || exit 1
rm TestSession/deleted.txt || exit 1
(cd TestSession && $BOAR ci -q -m"Räksmörgås") || exit 1

cat >expected.txt <<EOF
--------------------------------------------------------------------------------
!r5 \| TestSession \| .* \| 1 log line

Räksmörgås
--------------------------------------------------------------------------------
!r4 \| AnotherTestSession \| .* \| 1 log line

Single line comment
--------------------------------------------------------------------------------
!r3 \| AnotherTestSession \| .* \| 0 log lines

--------------------------------------------------------------------------------
!r2 \| TestSession \| .* \| 2 log lines

Comment line 1
Comment line 2
--------------------------------------------------------------------------------
!r1 \| TestSession \| .* \| 0 log lines

--------------------------------------------------------------------------------
!Finished in .* seconds
EOF
$BOAR log --repo=TESTREPO >output.txt || exit 1

txtmatch.py expected.txt output.txt || { 
    echo "Unexpected full repo log output"; exit 1; }


cat >expected.txt <<EOF
--------------------------------------------------------------------------------
!r5 \| TestSession \| .* \| 1 log line
Changed paths:
D deleted.txt
M modified.txt
A new.txt

Räksmörgås
--------------------------------------------------------------------------------
!r2 \| TestSession \| .* \| 2 log lines
Changed paths:
A deleted.txt
A modified.txt

Comment line 1
Comment line 2
--------------------------------------------------------------------------------
!r1 \| TestSession \| .* \| 0 log lines
Changed paths:

--------------------------------------------------------------------------------
!Finished in .* seconds
EOF

$BOAR log --repo=TESTREPO -v TestSession >output.txt || exit 1

txtmatch.py expected.txt output.txt || { 
    echo "Unexpected full repo log -v output"; exit 1; }

cat >expected.txt <<EOF
--------------------------------------------------------------------------------
!r2 \| TestSession \| .* \| 2 log lines

Comment line 1
Comment line 2
--------------------------------------------------------------------------------
!r1 \| TestSession \| .* \| 0 log lines

--------------------------------------------------------------------------------
!Finished in .* seconds
EOF

$BOAR log --repo=TESTREPO TestSession -r:4 >output.txt || exit 1

txtmatch.py expected.txt output.txt || { 
    echo "Unexpected range :4 log output"; exit 1; }

cat >expected.txt <<EOF
--------------------------------------------------------------------------------
!r2 \| TestSession \| .* \| 2 log lines

Comment line 1
Comment line 2
--------------------------------------------------------------------------------
!r1 \| TestSession \| .* \| 0 log lines

--------------------------------------------------------------------------------
!Finished in .* seconds
EOF

cat >expected.txt <<EOF
--------------------------------------------------------------------------------
!r5 \| TestSession \| .* \| 1 log line

Räksmörgås
--------------------------------------------------------------------------------
!Finished in .* seconds
EOF

$BOAR log --repo=TESTREPO TestSession -r4: >output.txt || exit 1

txtmatch.py expected.txt output.txt || { 
    echo "Unexpected range 4: log output"; exit 1; }

$BOAR log --repo=TESTREPO TestSession -r5 >output.txt || exit 1

txtmatch.py expected.txt output.txt || { 
    echo "Unexpected range 5 log output"; exit 1; }

#
# Testing different repo specfications priority (command
# line, workdir, environment)
#

$BOAR mkrepo REPO_WORKDIR || exit 1
$BOAR --repo=REPO_WORKDIR mksession WorkdirRepo || exit 1
$BOAR mkrepo REPO_CMDLINE || exit 1
$BOAR --repo=REPO_CMDLINE mksession CmdlineRepo || exit 1
$BOAR mkrepo REPO_ENV || exit 1
$BOAR --repo=REPO_ENV mksession EnvRepo || exit 1

$BOAR --repo=REPO_WORKDIR co WorkdirRepo || { echo "Couldn't check out WorkdirRepo"; exit 1; }

$BOAR log && { echo "log without repo should fail"; exit 1; }
$BOAR log | grep "ERROR: You must use this command in a workdir or specify a repository to operate on" || { 
    echo "log without repo gave unexpected error message"; exit 1; }
( REPO_PATH=REPO_ENV $BOAR log | grep EnvRepo ) || { echo "EnvRepo log failed"; exit 1; }
( $BOAR --repo=REPO_CMDLINE log | grep CmdlineRepo ) || { echo "CmdlineRepo log failed"; exit 1; }
( cd WorkdirRepo; $BOAR log | grep WorkdirRepo ) || { echo "WorkdirRepo log failed"; exit 1; }

REPO_ENV=`pwd`/REPO_ENV
REPO_CMDLINE=`pwd`/REPO_CMDLINE

( REPO_PATH=REPO_ENV $BOAR --repo=$REPO_CMDLINE log | grep CmdlineRepo ) || { 
    echo "Cmdline should have priority for cmdline+env"; exit 1; }
( cd WorkdirRepo; $BOAR --repo=$REPO_CMDLINE log | grep CmdlineRepo ) || { 
    echo "Cmdline should have priority for cmdline+workdir"; exit 1; }
( cd WorkdirRepo; REPO_PATH=$REPO_ENV $BOAR log | grep WorkdirRepo ) || {
    echo "WorkdirRepo should have priority for workdir+env"; exit 1; }
( cd WorkdirRepo; REPO_PATH=$REPO_ENV $BOAR --repo=$REPO_CMDLINE log | grep CmdlineRepo ) || { 
    echo "Cmdline should have priority for workdir+env+cmdline"; exit 1; }

REPO_PATH=REPO_ENV $BOAR log . && { echo "Log for '.' should fail for env repo"; exit 1; }
$BOAR --repo=REPO_CMDLINE log . && { echo "Log for '.' should fail for cmdline repo"; exit 1; }
( cd WorkdirRepo; $BOAR log . | grep WorkdirRepo ) || { echo "WorkdirRepo log for '.' failed"; exit 1; }

#
# Test workdir log
#

cat >expected.txt <<EOF
--------------------------------------------------------------------------------
!r3 \| WorkdirRepo \| .* \| 1 log line
Changed paths:
A å/file2.txt

Added file2.txt
--------------------------------------------------------------------------------
!r2 \| WorkdirRepo \| .* \| 1 log line
Changed paths:
A å/ä/ö/file1.txt

Added a subdir and file1.txt
--------------------------------------------------------------------------------
!r1 \| WorkdirRepo \| .* \| 0 log lines
Changed paths:

--------------------------------------------------------------------------------
!Finished in .* seconds
EOF

mkdir -p WorkdirRepo/å/ä/ö
echo "Some contents 1" >WorkdirRepo/å/ä/ö/file1.txt
(cd WorkdirRepo && $BOAR ci -q -m"Added a subdir and file1.txt") || exit 1
echo "Some contents 2" >WorkdirRepo/å/file2.txt
(cd WorkdirRepo && $BOAR ci -q -m"Added file2.txt") || exit 1
(cd WorkdirRepo && $BOAR log -v .) | cat >output.txt || exit 1
txtmatch.py expected.txt output.txt || { echo "Unexpected workdir log"; exit 1; }

cat >expected.txt <<EOF
!r3 \| WorkdirRepo \| .* \| 1 log line
EOF

(cd WorkdirRepo && $BOAR log å/file2.txt ) | grep log >output.txt || exit 1
txtmatch.py expected.txt output.txt || { echo "Unexpected workdir log for file2"; exit 1; }

cat >expected.txt <<EOF
!r2 \| WorkdirRepo \| .* \| 1 log line
EOF
$BOAR --repo=REPO_WORKDIR co WorkdirRepo/å/ä/ö räksmörgås || exit 1
(cd räksmörgås && $BOAR log . ) | grep log >output.txt || exit 1
txtmatch.py expected.txt output.txt || { echo "Unexpected offset workdir log"; exit 1; }

#

cat >expected.txt <<EOF
!r3 \| WorkdirRepo \| .* \| 1 log line
!r2 \| WorkdirRepo \| .* \| 1 log line
EOF
$BOAR --repo=REPO_WORKDIR co WorkdirRepo/å räksmörgås2 || exit 1
(cd räksmörgås2 && $BOAR log . ) | grep log >output.txt || exit 1
txtmatch.py expected.txt output.txt || { echo "Unexpected offset 2 workdir log"; exit 1; }

#

cat >expected.txt <<EOF
!r2 \| WorkdirRepo \| .* \| 1 log line
EOF
(cd räksmörgås2 && $BOAR log ä/ö/. ) | grep log >output.txt || exit 1
txtmatch.py expected.txt output.txt || { echo "Unexpected offset + subpath workdir log"; exit 1; }

cat >expected.txt <<EOF
!r3 \| WorkdirRepo \| .* \| 1 log line
!r2 \| WorkdirRepo \| .* \| 1 log line
!r1 \| WorkdirRepo \| .* \| 0 log lines
EOF
(cd räksmörgås2 && $BOAR log ) | grep log >output.txt || exit 1
txtmatch.py expected.txt output.txt || { echo "Unexpected offset workdir full log"; exit 1; }

exit 0 # All is well
