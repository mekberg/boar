# Test that the truncate command behaves as expected.
set -e

$BOAR mkrepo TESTREPO || exit 1
$BOAR mksession --repo=TESTREPO TestSession || exit 1
$BOAR --repo=TESTREPO co TestSession || exit 1
$BOAR mksession --repo=TESTREPO AnotherTestSession || exit 1
$BOAR --repo=TESTREPO co AnotherTestSession || exit 1

echo "Rev 3" >TestSession/r3.txt || exit 1
(cd TestSession && $BOAR ci -q) || exit 1

rm TestSession/r3.txt || exit 1
echo "Rev 4" >TestSession/r4.txt || exit 1
(cd TestSession && $BOAR ci -q) || exit 1

echo "Another file" >AnotherTestSession/another.txt || exit 1
(cd AnotherTestSession && $BOAR ci -q) || exit 1

rm TestSession/r4.txt || exit 1
echo "Rev 6" >TestSession/r6.txt || exit 1
(cd TestSession && $BOAR ci -q) || exit 1

echo "Yet another file" >AnotherTestSession/yet_another.txt || exit 1
rm AnotherTestSession/another.txt || exit 1
mkdir AnotherTestSession/subdir/ || exit 1
echo "Subdir file" >AnotherTestSession/subdir/subdir_file.txt || exit 1
(cd AnotherTestSession && $BOAR ci -q) || exit 1

$BOAR mksession --repo=TESTREPO EmptySession || exit 1

##################

cat >expected.txt <<EOF
AnotherTestSession (3 revs)
TestSession (4 revs)
EmptySession (1 revs)
!Finished in .* seconds
EOF
$BOAR --repo=TESTREPO ls >output.txt 2>&1 || { 
    cat output.txt; echo "ls with no args failed"; exit 1; }
txtmatch.py expected.txt output.txt || { 
    echo "ls with no args gave unexpected output"; exit 1; }

##################

cat >expected.txt <<EOF
r6.txt
!Finished in .* seconds
EOF
$BOAR --repo=TESTREPO ls TestSession >output.txt 2>&1 || { 
    cat output.txt; echo "ls TestSession failed"; exit 1; }
txtmatch.py expected.txt output.txt || { 
    echo "ls TestSession gave unexpected output"; exit 1; }

##################

cat >expected.txt <<EOF
r3.txt
!Finished in .* seconds
EOF
$BOAR --repo=TESTREPO ls -r3 TestSession >output.txt 2>&1 || { 
    cat output.txt; echo "ls -r3 TestSession failed"; exit 1; }
txtmatch.py expected.txt output.txt || { 
    echo "ls -r3 TestSession gave unexpected output"; exit 1; }

##################

cat >expected.txt <<EOF
ERROR: No such file or directory found in session: DoesNotExist
!Finished in .* seconds
EOF
$BOAR --repo=TESTREPO ls TestSession/DoesNotExist >output.txt 2>&1 && { 
    cat output.txt; echo "ls for non-existing path should fail"; exit 1; }
txtmatch.py expected.txt output.txt || { 
    echo "ls for non-existing path gave unexpected output"; exit 1; }

##################

cat >expected.txt <<EOF
ERROR: There is no session with the name 'NonExistingSession'
!Finished in .* seconds
EOF
$BOAR --repo=TESTREPO ls NonExistingSession >output.txt 2>&1 && { 
    cat output.txt; echo "ls for non-existing session should fail"; exit 1; }
txtmatch.py expected.txt output.txt || { 
    echo "ls for non-existing session gave unexpected output"; exit 1; }

##################

cat >expected.txt <<EOF
!Finished in .* seconds
EOF
$BOAR --repo=TESTREPO ls EmptySession >output.txt 2>&1 || { 
    cat output.txt; echo "ls EmptySession failed"; exit 1; }
txtmatch.py expected.txt output.txt || { 
    echo "ls EmptySession gave unexpected output"; exit 1; }
$BOAR --repo=TESTREPO ls EmptySession/ >output.txt 2>&1 || { 
    cat output.txt; echo "ls EmptySession failed"; exit 1; }
txtmatch.py expected.txt output.txt || { 
    echo "ls EmptySession/ gave unexpected output"; exit 1; }

###################

cat >expected.txt <<EOF
ERROR: There is no such session/revision
!Finished in .* seconds
EOF
$BOAR --repo=TESTREPO ls -r1 EmptySession >output.txt 2>&1 && { 
    cat output.txt; echo "ls for session/revision mismatch should fail"; exit 1; }
txtmatch.py expected.txt output.txt || { 
    echo "ls for session/revision mismatch gave unexpected output"; exit 1; }

###################

cat >expected.txt <<EOF
subdir/
yet_another.txt
!Finished in .* seconds
EOF
$BOAR --repo=TESTREPO ls AnotherTestSession/ >output.txt 2>&1 || { 
    cat output.txt; echo "ls AnotherTestSession/ failed"; exit 1; }
txtmatch.py expected.txt output.txt || { 
    echo "ls AnotherTestSession/ gave unexpected output"; exit 1; }

###################

cat >expected.txt <<EOF
subdir/
yet_another.txt 1kB
!Finished in .* seconds
EOF
$BOAR --repo=TESTREPO ls -v AnotherTestSession/ >output.txt 2>&1 || { 
    cat output.txt; echo "ls -v AnotherTestSession/ failed"; exit 1; }
txtmatch.py expected.txt output.txt || { 
    echo "ls -v AnotherTestSession/ gave unexpected output"; exit 1; }

###################

cat >expected.txt <<EOF
subdir_file.txt
!Finished in .* seconds
EOF
$BOAR --repo=TESTREPO ls AnotherTestSession/subdir/ >output.txt 2>&1 || { 
    cat output.txt; echo "ls AnotherTestSession/subdir/ failed"; exit 1; }
txtmatch.py expected.txt output.txt || { 
    echo "ls AnotherTestSession/subdir/ gave unexpected output"; exit 1; }

exit 0 # All is well
