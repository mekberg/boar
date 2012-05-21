export REPO_PATH="`pwd`/TESTREPO" 
$BOAR mkrepo $REPO_PATH || exit 1

cat >expected_duplicate_msg.txt <<EOF
ERROR: There already exists a session named 'SimpleSession'
!Finished in .* seconds
EOF

$BOAR mksession SimpleSession || { echo "mksession for simple name failed"; exit 1; }
$BOAR mksession SimpleSession && { echo "mksession for existing name should fail"; exit 1; }
$BOAR mksession SimpleSession | txtmatch.py expected_duplicate_msg.txt ||
    { echo "Unexpected error message for duplicate session"; exit 1; }
$BOAR mksession "#Räk smörgås" || { echo "mksession for tricky name failed"; exit 1; }
$BOAR mksession "#Räk smörgås" && { echo "mksession for existing tricky name should fail"; exit 1; }
$BOAR mksession "Simple/Session" && { echo "mksession for names containing slash should fail"; exit 1; }
$BOAR mksession "Simple/" && { echo "mksession for names containing slash should fail"; exit 1; }
$BOAR mksession "/Simple" && { echo "mksession for names containing slash should fail"; exit 1; }
$BOAR mksession "\\Simple" && { echo "mksession for names containing backslash should fail"; exit 1; }
$BOAR mksession "Simple\\" && { echo "mksession for names containing backslash should fail"; exit 1; }
$BOAR mksession "Sim\\ple" && { echo "mksession for names containing backslash should fail"; exit 1; }
$BOAR mksession "__Simple" && { echo "mksession for names starting with double underscore should fail"; exit 1; }
$BOAR mksession "_Sim_ple_" || { echo "most session names with underscores are allowed"; exit 1; }

$BOAR mksession "" >output.txt 2>&1 && { echo "Zero length session name should fail"; exit 1; }
grep "ERROR: Session names must not be empty" output.txt || { echo "Unexpected error message for zero length name"; exit 1; }

$BOAR mksession " " >output.txt 2>&1 && { echo "Zero length session name should fail"; exit 1; }
grep "ERROR: Session names must not begin or end with whitespace" output.txt || { echo "Unexpected error message for zero length name"; exit 1; }

$BOAR mksession " Tjo" >output.txt 2>&1 && { echo "Zero length session name should fail"; exit 1; }
grep "ERROR: Session names must not begin or end with whitespace" output.txt || { echo "Unexpected error message for zero length name"; exit 1; }

$BOAR mksession "Tjo " >output.txt 2>&1 && { echo "Zero length session name should fail"; exit 1; }
grep "ERROR: Session names must not begin or end with whitespace" output.txt || { echo "Unexpected error message for zero length name"; exit 1; }

cat >expected_ls_output.txt <<EOF
#Räk smörgås (1 revs)
_Sim_ple_ (1 revs)
SimpleSession (1 revs)
!Finished in .* seconds
EOF

$BOAR ls >ls_output.txt || exit 1
txtmatch.py expected_ls_output.txt ls_output.txt || { echo "unexpected ls output"; exit 1; }

true
