export REPO_PATH="`pwd`/TESTREPO" 
$BOAR mkrepo $REPO_PATH || exit 1

$BOAR mksession SimpleSession || { echo "mksession for simple name failed"; exit 1; }
$BOAR mksession SimpleSession && { echo "mksession for existing name should fail"; exit 1; }
$BOAR mksession SimpleSession | grep "ERROR: There already exists a session named 'SimpleSession'" || \
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

$BOAR ls | head -n -1 >ls_output.txt || exit 1
diff - ls_output.txt <<EOF || { echo "unexpected ls output"; exit 1; }
#Räk smörgås (1 revs)
_Sim_ple_ (1 revs)
SimpleSession (1 revs)
EOF

true
