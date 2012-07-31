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
rm -r TestSession || exit 1

# Delete all the files

(cd Import && rm *.txt && $BOAR ci -q ) || exit 1

# Add one file per snapshot
echo f1b >Import/f1.txt || exit 1
(cd Import && $BOAR ci -q ) || exit 1 # Snapshot 5, 1 add, 1 total
echo f2b >Import/f2.txt || exit 1
(cd Import && $BOAR ci -q ) || exit 1 # Snapshot 6, 2 adds, 2 total
echo f3b >Import/f3.txt || exit 1
(cd Import && $BOAR ci -q ) || exit 1 # Snapshot 7, 3 adds, 3 total

# Modify one file per snapshot
echo f1c >Import/f1.txt || exit 1
(cd Import && $BOAR ci -q ) || exit 1 # Snapshot 8, 4 adds, 3 total
echo f2c >Import/f2.txt || exit 1
(cd Import && $BOAR ci -q ) || exit 1 # Snapshot 9, 5 adds, 3 total
echo f3c >Import/f3.txt || exit 1
(cd Import && $BOAR ci -q ) || exit 1 # Snapshot 10, 6 adds, 3 total -> trigger rebalancing

# Remove one file per snapshot
rm Import/f1.txt || exit 1
(cd Import && $BOAR ci -q ) || exit 1 # Snapshot 11, rebalanced due to previous 0-length snapshot
rm Import/f2.txt || exit 1
(cd Import && $BOAR ci -q ) || exit 1 # Snapshot 12, 1 remove, 1 total -> trigger rebalancing
rm Import/f3.txt || exit 1
(cd Import && $BOAR ci -q ) || exit 1 # Snapshot 13, rebalanced due to zero length

cat >expected.txt <<EOF
[1, null, "TestSession", "d41d8cd98f00b204e9800998ecf8427e", null, false]
[2, null, "TestSession", "4a7ce3aa4120073bf080e9e3e3a6ca20", null, false]
[3, null, "TestSession", "37ee2eee44cd5c3f84e337b3e0671825", null, false]
[4, null, "TestSession", "d41d8cd98f00b204e9800998ecf8427e", null, false]
[5, null, "TestSession", "ab48420a0aa5ade432dde008693f62fa", null, false]
[6, 5, "TestSession", "ddd428cf16b7bdc0cb4ff8d4590b18ea", null, false]
[7, 6, "TestSession", "6d2bf11e2f0e1eb98d152f4176cd8376", null, false]
[8, 7, "TestSession", "f09b15985a1f67806396d0c280ade184", null, false]
[9, 8, "TestSession", "389fac2a7ba5f88c13306fe157ef896a", null, false]
[10, null, "TestSession", "1412968c5df26f8bb3438662ae1bf8cb", null, false]
[11, null, "TestSession", "4b00b0cd6442b565f5d717fda9cc5092", null, false]
[12, null, "TestSession", "5c41d2ca0b977391192f0458085463f1", null, false]
[13, null, "TestSession", "d41d8cd98f00b204e9800998ecf8427e", null, false]
!Finished in (.*) seconds
EOF

$BOAR --repo="$REPO_PATH" list --dump >output.txt || exit 1

txtmatch.py expected.txt output.txt || {
    echo "Unexpected dump contents"; exit 1; }
rm output.txt || exit 1

# Test a clone
$BOAR clone $REPO_PATH CLONE || exit 1
$BOAR --repo=CLONE list --dump >output.txt || exit 1
txtmatch.py expected.txt output.txt || {
    echo "Unexpected clone dump contents"; exit 1; }

true
