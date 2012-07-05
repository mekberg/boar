set -e

export REPO_PATH=MANIFEST_TEST_REPO
$BOAR mkrepo $REPO_PATH || exit 1
$BOAR mksession TestSession || exit 1
mkdir Import || exit 1

echo -- Testing simple case happy path

echo "avocado" >Import/file.txt || exit 1

cat >Import/manifest-md5.txt <<EOF
c6f3a2db52a478d9d00fd1059dac6e0a  file.txt
EOF

cat >expected.txt <<EOF
NOTICE: Using manifest file manifest-md5.txt
Sending file.txt
Sending manifest-md5.txt
Checked in session id 2
!Finished in (.*) seconds
EOF

$BOAR import -wq Import TestSession >output.txt 2>&1 || exit 1

txtmatch.py expected.txt output.txt || {
    echo "Import with simple manifest gave unexpected message"; exit 1; }

echo -- Testing manifest mismatch

cat >expected.txt <<EOF
NOTICE: Using manifest file manifest-md5.txt
ERROR: File file.txt contents conflicts with manifest
!Finished in (.*) seconds
EOF

echo "not avocado" >Import/file.txt || exit 1
(cd Import && $BOAR ci -q) >output.txt 2>&1 && { cat output.txt; echo "Erronous manifest should fail"; exit 1; }

txtmatch.py expected.txt output.txt || {
    echo "Import with manifest mismatch gave unexpected message"; exit 1; }

echo -- Testing manifest conflict
cat >Import/manifest-md5-efe6d1786f752ff3efd364dbd2d52239.txt <<EOF
aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa  file.txt
EOF

cat >expected.txt <<EOF
NOTICE: Using manifest file manifest-md5-efe6d1786f752ff3efd364dbd2d52239.txt
NOTICE: Using manifest file manifest-md5.txt
ERROR: Conflicting manifests for file file.txt
!Finished in (.*) seconds
EOF

(cd Import && $BOAR ci -q) >output.txt 2>&1 && { cat output.txt; echo "Conflicting manifests should fail"; exit 1; }

txtmatch.py expected.txt output.txt || {
    echo "Import with manifest conflict gave unexpected message"; exit 1; }

echo -- Testing manifest checksum error
# Creating manifest with wrong checksum in name
cat >expected.txt <<EOF
ERROR: Contents of manifest file 'manifest-md5-efe6d1786f752ff3efd364dbd2d52239.txt' does not match the expected checksum
!Finished in .* seconds
EOF

cat >Import/manifest-md5-efe6d1786f752ff3efd364dbd2d52239.txt <<EOF
bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb  file.txt
EOF

(cd Import && $BOAR ci -q) >output.txt 2>&1 && { cat output.txt; echo "Conflicting manifests should fail"; exit 1; }

txtmatch.py expected.txt output.txt || {
    echo "Import with manifest conflict gave unexpected message"; exit 1; }
rm Import/manifest-md5-efe6d1786f752ff3efd364dbd2d52239.txt || exit 1

echo -- Testing redundant manifests with matching file
cp Import/manifest-md5.txt Import/manifest-md5-6f0d05d79c11595917d4ebe31a18fbb1.txt || exit 1
echo "avocado" >Import/file.txt || exit 1
cat >expected.txt <<EOF
NOTICE: Using manifest file manifest-md5.txt
NOTICE: Using manifest file manifest-md5-6f0d05d79c11595917d4ebe31a18fbb1.txt
Sending manifest-md5-6f0d05d79c11595917d4ebe31a18fbb1.txt
Checked in session id 3
!Finished in .* seconds
EOF

(cd Import && $BOAR ci -q) >output.txt 2>&1 || { cat output.txt; echo "Redundant manifests should succeed"; exit 1; }
txtmatch.py expected.txt output.txt || {
    echo "Import with redundant manifests gave unexpected message"; exit 1; }

echo "All is well"
true

