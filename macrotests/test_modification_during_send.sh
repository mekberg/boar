set -e
$BOAR mkrepo TESTREPO || exit 1
$BOAR --repo=TESTREPO mksession "Session" || exit 1
$BOAR --repo=TESTREPO co "Session" || exit 1

cat >modify_open_raw.py <<"EOF"
def send_file_hook_modify(filename):
    assert filename.endswith("avocado.txt")
    with open(filename, "wb") as f:
        f.write("avoCado")
workdir._send_file_hook = send_file_hook_modify
EOF

echo -n "avocado" > Session/avocado.txt || exit 1

cat > expected.txt <<EOF
Sending avocado.txt
ERROR: File changed during commit: avocado.txt
!Finished in .* seconds
EOF

( cd Session && $BOAR --EXEC ../modify_open_raw.py ci -q ) >output.txt 2>&1 && {
    cat output.txt; echo "Modified commit should fail"; exit 1; }

txtmatch.py expected.txt output.txt || { echo "Unexpected error message for file modified during commit"; exit 1; }


echo -n "avocado too long" > Session/avocado.txt || exit 1

( cd Session && $BOAR --EXEC ../modify_open_raw.py ci -q ) >output.txt 2>&1 && {
    cat output.txt; echo "Modified commit (too long) should fail"; exit 1; }

txtmatch.py expected.txt output.txt || { echo "Unexpected error message for too long file modified during commit"; exit 1; }

true
