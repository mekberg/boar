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

$BOAR import -wq Import TestSession >output.txt 2>&1 || { cat output.txt; echo "Happy path failed"; exit 1; }

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
cat >Import/manifest-efe6d1786f752ff3efd364dbd2d52239.md5 <<EOF
aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa  file.txt
EOF

cat >expected.txt <<EOF
NOTICE: Using manifest file manifest-efe6d1786f752ff3efd364dbd2d52239.md5
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
ERROR: Contents of manifest file 'manifest-efe6d1786f752ff3efd364dbd2d52239.md5' does not match the expected checksum
!Finished in .* seconds
EOF

cat >Import/manifest-efe6d1786f752ff3efd364dbd2d52239.md5 <<EOF
bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb  file.txt
EOF

(cd Import && $BOAR ci -q) >output.txt 2>&1 && { cat output.txt; echo "Conflicting manifests should fail"; exit 1; }

txtmatch.py expected.txt output.txt || {
    echo "Import with manifest conflict gave unexpected message"; exit 1; }
rm Import/manifest-efe6d1786f752ff3efd364dbd2d52239.md5 || exit 1

echo -- Testing redundant manifests with matching file
cp Import/manifest-md5.txt Import/manifest-6f0d05d79c11595917d4ebe31a18fbb1.md5 || exit 1
echo "avocado" >Import/file.txt || exit 1
cat >expected.txt <<EOF
NOTICE: Using manifest file manifest-md5.txt
NOTICE: Using manifest file manifest-6f0d05d79c11595917d4ebe31a18fbb1.md5
Sending manifest-6f0d05d79c11595917d4ebe31a18fbb1.md5
Checked in session id 3
!Finished in .* seconds
EOF

(cd Import && $BOAR ci -q) >output.txt 2>&1 || { cat output.txt; echo "Redundant manifests should succeed"; exit 1; }
txtmatch.py expected.txt output.txt || {
    echo "Import with redundant manifests gave unexpected message"; exit 1; }

echo -- Testing unsupported bagit-style manifest
cat >Import/manifest-sha1.txt <<EOF || exit 1
68fd76bef43084330620e91d3ebcc0ad8c9ec1cd  Import/file.txt
EOF

cat >expected.txt <<EOF
WARNING: Found manifest file manifest-sha1.txt, but hash type 'sha1' is not
         supported yet. Ignoring.
NOTICE: Using manifest file manifest-md5.txt
NOTICE: Using manifest file manifest-6f0d05d79c11595917d4ebe31a18fbb1.md5
Sending manifest-sha1.txt
Checked in session id 4
!Finished in .* seconds
EOF
(cd Import && $BOAR ci -q) >output.txt 2>&1 || { 
    cat output.txt; echo "Unsupported manifests should succeed with warning"; exit 1; }
txtmatch.py expected.txt output.txt || {
    echo "Unsupported manifests gave unexpected message"; exit 1; }

echo -- Testing subdir manifest
(mkdir subdir && mv Import/* subdir && mv subdir Import) || exit 1
(cd Import && $BOAR status) || exit 1
(cd Import && $BOAR ci) || ( echo "Commit for manifest in subdir failed"; exit 1; )

echo "All is well"
true

