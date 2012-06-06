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

exit 0 # All is well
