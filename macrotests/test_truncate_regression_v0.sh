# Test that cloning of legacy repo with some quirks (meta sessions,
# legal missing snapshots) works as expected.

testdir="`pwd`"
tar xzf $BOARTESTHOME/truncate_regression_v0.tar.gz || exit 1
REPO=$testdir/TESTREPO
rm -r $REPO/sessions/2

cat <<EOF >expected_original_dump.txt
[1, null, "Test", "d41d8cd98f00b204e9800998ecf8427e", null, false]
[2, null, "__deleted", "d41d8cd98f00b204e9800998ecf8427e", null, true]
[3, null, "__meta_Test", "d41d8cd98f00b204e9800998ecf8427e", null, false]
[4, 3, "__meta_Test", "a80b8735575eb12d18b30a54ede69d43", null, false]
[5, 4, "__meta_Test", "c4b1be8a9ca38142ccfa3c506fa14048", null, false]
[6, 1, "Test", "f341faac49bdd76cc11a5739680efb78", null, false]
!Finished in .* seconds
EOF

cat <<EOF >expected_original_Test_list.txt
Revision id 1 (Sun May  6 10:44:48 2012), 0 files, (standalone) Log: <not specified>
Revision id 6 (Sun May  6 10:55:53 2012), 1 files, (delta) Log: <not specified>
!Finished in .* seconds
EOF

cat <<EOF >expected_original_meta_list.txt
Revision id 3 (Sun May  6 10:46:28 2012), 0 files, (standalone) Log: <not specified>
Revision id 4 (Sun May  6 10:46:28 2012), 1 files, (delta) Log: <not specified>
Revision id 5 (Sun May  6 10:49:12 2012), 1 files, (delta) Log: <not specified>
!Finished in .* seconds
EOF


# ----

cat <<EOF >expected_truncated_dump.txt
[1, null, "__deleted", "d41d8cd98f00b204e9800998ecf8427e", null, true]
[2, null, "__deleted", "d41d8cd98f00b204e9800998ecf8427e", null, true]
[3, null, "__meta_Test", "d41d8cd98f00b204e9800998ecf8427e", null, false]
[4, 3, "__meta_Test", "a80b8735575eb12d18b30a54ede69d43", null, false]
[5, 4, "__meta_Test", "c4b1be8a9ca38142ccfa3c506fa14048", null, false]
[6, null, "__deleted", "d41d8cd98f00b204e9800998ecf8427e", null, true]
[7, null, "__deleted", "d41d8cd98f00b204e9800998ecf8427e", null, true]
[8, null, "Test", "b059a88bc42ab0176ce03f48b3c4aeb4", null, false]
!Finished in .* seconds
EOF

cat <<EOF >expected_truncated_Test_list.txt
!Revision id 8 (.*), 2 files, \(standalone\) Log: <not specified>
!Finished in .* seconds
EOF

# ------------
$BOAR --repo=$REPO list --dump >output.txt || exit 1
txtmatch.py expected_original_dump.txt output.txt || exit 1
$BOAR --repo=$REPO list Test >output.txt || exit 1
txtmatch.py expected_original_Test_list.txt output.txt || exit 1
$BOAR --repo=$REPO list __meta_Test >output.txt || exit 1
txtmatch.py expected_original_meta_list.txt output.txt || exit 1
# ------------

$BOAR clone $REPO CLONE1 || exit 1
$BOAR clone CLONE1 CLONE2 || exit 1

# ------------ Test that the last clone looks ok
$BOAR --repo=CLONE2 list --dump >output.txt || exit 1
txtmatch.py expected_original_dump.txt output.txt || exit 1
$BOAR --repo=CLONE2 list Test >output.txt || exit 1
txtmatch.py expected_original_Test_list.txt output.txt || exit 1
$BOAR --repo=CLONE2 list __meta_Test >output.txt || exit 1
txtmatch.py expected_original_meta_list.txt output.txt || exit 1
# -------------

touch $REPO/ENABLE_PERMANENT_ERASE CLONE1/ENABLE_PERMANENT_ERASE CLONE2/ENABLE_PERMANENT_ERASE || exit 1

$BOAR co --repo=$REPO Test || exit 1
# Make sure that the first snapshot to be cloned is a deleted snapshot - a tricky case
(cd Test && echo "New rev" >data.txt && $BOAR ci -q) || exit 1
rm -r Test || exit 1
$BOAR truncate --repo=$REPO Test || exit 1

# Now test replication
$BOAR clone $REPO CLONE_new || exit 1
$BOAR clone $REPO CLONE1 || exit 1
$BOAR clone CLONE1 CLONE2 || exit 1


# ------------ Test that the clones looks ok
for clone in CLONE_new CLONE1 CLONE2; do
    echo "Testing repo $clone"
    $BOAR --repo=$clone list --dump >output.txt || exit 1
    txtmatch.py expected_truncated_dump.txt output.txt || exit 1
    $BOAR --repo=$clone list Test >output.txt || exit 1
    txtmatch.py expected_truncated_Test_list.txt output.txt || exit 1
    $BOAR --repo=$clone list __meta_Test >output.txt || exit 1
    txtmatch.py expected_original_meta_list.txt output.txt || exit 1
done

echo "All OK"
exit 0