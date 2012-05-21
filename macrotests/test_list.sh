# Test that the list command works

$BOAR mkrepo TESTREPO || exit 1
$BOAR mksession --repo=TESTREPO TestSession || exit 1
$BOAR --repo=TESTREPO co TestSession || exit 1
$BOAR mksession --repo=TESTREPO AnotherTestSession || exit 1
$BOAR --repo=TESTREPO co AnotherTestSession || exit 1

echo "Rev 2" >TestSession/r2.txt || exit 1
(cd TestSession && $BOAR ci -q) || exit 1

rm TestSession/r2.txt || exit 1
echo "Rev 3" >TestSession/r3.txt || exit 1
(cd TestSession && $BOAR ci -q) || exit 1

echo "Another file" >AnotherTestSession/another.txt || exit 1
(cd AnotherTestSession && $BOAR ci -q) || exit 1

rm TestSession/r3.txt || exit 1
echo "Rev 4" >TestSession/r4.txt || exit 1
(cd TestSession && $BOAR ci -q) || exit 1

echo "Yet another file" >AnotherTestSession/yet_another.txt || exit 1
rm AnotherTestSession/another.txt || exit 1
(cd AnotherTestSession && $BOAR ci -q) || exit 1

cp -an TESTREPO TESTREPO_truncated || exit 1
touch TESTREPO_truncated/ENABLE_PERMANENT_ERASE || exit 1
$BOAR --repo=TESTREPO_truncated truncate TestSession || { echo "Truncation failed"; exit 1; }
$BOAR --repo=TESTREPO_truncated verify || { echo "Truncated repo failed verify"; exit 1; }

cat >expected_dump_msg.txt <<EOF
[1, null, "__deleted", "d41d8cd98f00b204e9800998ecf8427e", null, true]
[2, null, "AnotherTestSession", "d41d8cd98f00b204e9800998ecf8427e", null, false]
[3, null, "__deleted", "d41d8cd98f00b204e9800998ecf8427e", null, true]
[4, null, "__deleted", "d41d8cd98f00b204e9800998ecf8427e", null, true]
[5, 2, "AnotherTestSession", "0e997688909a2d27886dfdeaa627b560", null, false]
[6, null, "__deleted", "d41d8cd98f00b204e9800998ecf8427e", null, true]
[7, 5, "AnotherTestSession", "31a44468d11cc4924b15c5d106410a63", null, false]
[8, null, "TestSession", "ed6b2754f96ba1e3c1cf10ab3e492b03", null, false]
!Finished in .* seconds
EOF

$BOAR --repo=TESTREPO_truncated list --dump >dump_msg.txt 2>&1 || { echo "List command failed"; exit 1; }
txtmatch.py expected_dump_msg.txt dump_msg.txt || { echo "Unexpected list result"; exit 1; }

cat >expected.txt <<EOF
AnotherTestSession (3 revs)
TestSession (1 revs)
!Finished in .* seconds
EOF

$BOAR --repo=TESTREPO_truncated list >output.txt 2>&1 || { echo "List command failed"; exit 1; }
txtmatch.py expected.txt output.txt || { echo "Unexpected list result"; exit 1; }

cat >expected.txt <<EOF
!Revision id 8 \(.*\), 1 files, \(standalone\) Log: <not specified>
!Finished in .* seconds
EOF

$BOAR --repo=TESTREPO_truncated list TestSession >output.txt 2>&1 || { echo "List command failed"; exit 1; }
txtmatch.py expected.txt output.txt || { echo "Unexpected list result"; exit 1; }

cat >expected.txt <<EOF
!Revision id 2 \(.*\), 0 files, \(standalone\) Log: <not specified>
!Revision id 5 \(.*\), 1 files, \(delta\) Log: <not specified>
!Revision id 7 \(.*\), 1 files, \(delta\) Log: <not specified>
!Finished in .* seconds
EOF

$BOAR --repo=TESTREPO_truncated list AnotherTestSession >output.txt 2>&1 || { echo "List command failed"; exit 1; }
txtmatch.py expected.txt output.txt || { echo "Unexpected list result"; exit 1; }

cat >expected.txt <<EOF
another.txt 1k
!Finished in .* seconds
EOF

$BOAR --repo=TESTREPO_truncated list AnotherTestSession 5 >output.txt 2>&1 || { echo "List command failed"; exit 1; }
txtmatch.py expected.txt output.txt || { echo "Unexpected list result"; exit 1; }

exit 0 # All is well
