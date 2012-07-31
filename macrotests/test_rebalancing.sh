set -e

export REPO_PATH=REBALANCE_TEST_REPO
$BOAR mkrepo $REPO_PATH || exit 1
$BOAR mksession TestSession || exit 1
mkdir Import || exit 1

echo f1 >Import/f1.txt || exit 1
echo f2 >Import/f2.txt || exit 1
echo f3 >Import/f3.txt || exit 1

echo "Importing..."
$BOAR import -w Import TestSession || exit 1 
# Created rev 2: 0 removes, 3 adds, 3 total

echo "Modifying..."
echo f1a >Import/f1.txt || exit 1 # Modified
rm Import/f2.txt || exit 1        # Deleted
# Import/f3.txt                   # Unchanged
echo f4 >Import/f4.txt || exit 1  # New

(cd Import && $BOAR ci -q ) || exit 1

$BOAR co TestSession || exit 1
md5sum -c - <<EOF || exit 1
9de8f190424096e93e26ede2f52cab59  TestSession/f1.txt
3385b5d27d4c2923e9cde7ea53f28e2b  TestSession/f3.txt
5f3022d3a5cbcbf30a75c33ea39b2622  TestSession/f4.txt
EOF
test ! -e TestSession/f2.txt || exit 1

# Delete all the files

(cd Import && rm *.txt && $BOAR ci -q ) || exit 1

cat >expected.txt <<EOF
[1, null, "TestSession", "d41d8cd98f00b204e9800998ecf8427e", null, false]
[2, null, "TestSession", "4a7ce3aa4120073bf080e9e3e3a6ca20", null, false]
[3, null, "TestSession", "37ee2eee44cd5c3f84e337b3e0671825", null, false]
[4, null, "TestSession", "d41d8cd98f00b204e9800998ecf8427e", null, false]
!Finished in (.*) seconds
EOF

$BOAR --repo="$REPO_PATH" list --dump >output.txt || exit 1

txtmatch.py expected.txt output.txt || {
    echo "Unexpected dump contents"; exit 1; }

true
