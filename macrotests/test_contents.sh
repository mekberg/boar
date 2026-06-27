# Test that the contents command behaves as expected.
set -e

export REPO_PATH=`pwd`/TESTREPO
$BOAR mkrepo $REPO_PATH
$BOAR mksession RäksmörgåsSession
$BOAR co RäksmörgåsSession

echo "Rev 2 file" >RäksmörgåsSession/r2.txt
echo "keep me" >RäksmörgåsSession/keep.txt
(cd RäksmörgåsSession && $BOAR ci -q)

echo "Rev 3 file" >RäksmörgåsSession/r3.txt
(cd RäksmörgåsSession && $BOAR ci -q)

# --md5sum of the latest revision must list all three files with correct
# checksums. Normalize boar's "<md5> *<name>" and md5sum's "<md5>  <name>"
# to a common form and compare sorted.
(cd RäksmörgåsSession && md5sum keep.txt r2.txt r3.txt) | sed 's/  / /' | sort >expected.txt
$BOAR contents --md5sum RäksmörgåsSession | sed 's/ \*/ /' | sort >output.txt
txtmatch.py expected.txt output.txt || { echo "Unexpected --md5sum output for latest revision"; exit 1; }

# -r selects an older revision (rev 2 has only two files).
(cd RäksmörgåsSession && md5sum keep.txt r2.txt) | sed 's/  / /' | sort >expected.txt
$BOAR contents -r 2 --md5sum RäksmörgåsSession | sed 's/ \*/ /' | sort >output.txt
txtmatch.py expected.txt output.txt || { echo "Unexpected --md5sum output for -r 2"; exit 1; }

# --punycode lets the session name be given in punycode form. It must produce
# the exact same result as the plain name.
PUNYNAME=$($PYTHON_BINARY -c "print('RäksmörgåsSession'.encode('punycode').decode('ascii'))")
$BOAR contents RäksmörgåsSession >plain.txt
$BOAR contents --punycode "$PUNYNAME" >puny.txt
txtmatch.py plain.txt puny.txt || { echo "--punycode gave different output than plain name"; exit 1; }

# An empty session must not crash: --md5sum gives no output, json gives [] files.
$BOAR mksession EmptySession
$BOAR contents --md5sum EmptySession >output.txt || { echo "contents --md5sum failed on empty session"; exit 1; }
test ! -s output.txt || { cat output.txt; echo "Empty session should produce no --md5sum lines"; exit 1; }

cat >expected.txt <<EOF
    "files": []
EOF
$BOAR contents EmptySession | grep '"files"' >output.txt || { echo "contents (json) failed on empty session"; exit 1; }
txtmatch.py expected.txt output.txt || { echo "Empty session json should have an empty files list"; exit 1; }

# A non-existing session must fail with a friendly error.
cat >expected.txt <<EOF
ERROR: No such session found: NoSuchSession
EOF
$BOAR contents NoSuchSession >output.txt 2>&1 && { cat output.txt; echo "contents of non-existing session should fail"; exit 1; }
txtmatch.py expected.txt output.txt || { echo "Unexpected error message for non-existing session"; exit 1; }

echo "All is well"
true
