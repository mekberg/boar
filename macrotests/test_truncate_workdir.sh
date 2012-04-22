# Test that a workdir belonging to a deleted snapshot works as
# expected.
set -e

$BOAR mkrepo TESTREPO || exit 1
touch TESTREPO/ENABLE_PERMANENT_ERASE || exit 1
$BOAR mksession --repo=TESTREPO TestSession || exit 1
$BOAR --repo=TESTREPO co TestSession || exit 1

cat >workdir_original_contents.txt <<EOF
repo_deleted.txt:original 3
repo_modified.txt:original 2
unchanged.txt:original 1
wd_modified.txt:wd locally modified
EOF

cd TestSession || exit 1
echo "original 1" >unchanged.txt || exit 1     # Unchanged
echo "original 2" >repo_modified.txt || exit 1 # Modified in a later commit from another workdir
echo "original 3" >repo_deleted.txt || exit 1  # Deleted in a later commit from another workdir
echo "original 4" >wd_modified.txt || exit 1   # Modified in workdir after commit
echo "original 5" >wd_deleted.txt || exit 1    # Deleted in workdir after commit
$BOAR ci || exit 1
echo "wd locally modified" >wd_modified.txt || exit 1
rm wd_deleted.txt || exit 1
cd ..

(cd TestSession && grep . *.txt) >output.txt || exit 1
txtmatch.py workdir_original_contents.txt output.txt || { echo "Unexpected workdir initial contents"; exit 1; }

$BOAR --repo=TESTREPO co TestSession TestSessionModify || exit 1
cd TestSessionModify
echo "modified" >repo_modified.txt || exit 1
rm repo_deleted.txt || exit 1
$BOAR ci || exit 1
cd ..

$BOAR --repo=TESTREPO truncate TestSession || exit 1

cat >expected.txt <<EOF
[1, null, "__deleted", "d41d8cd98f00b204e9800998ecf8427e", null, true]
[2, null, "__deleted", "d41d8cd98f00b204e9800998ecf8427e", null, true]
[3, null, "__deleted", "d41d8cd98f00b204e9800998ecf8427e", null, true]
[4, null, "TestSession", "5802b36c54f7136ce0a140ca7b946783", "Standalone snapshot", false]
!Finished in .* seconds
EOF
$BOAR --repo=TESTREPO list --dump >output.txt 2>&1 || { echo "Dump failed"; exit 1; }
txtmatch.py expected.txt output.txt || { echo "Output mismatch at line $LINENO"; exit 1; }


cat >expected.txt <<EOF
Using a work directory:
!   Workdir root: .*/TestSession
!   Repository: .*/TESTREPO
   Session: TestSession / 
   Revision: 2
!Finished in .* seconds
EOF
(cd TestSession && $BOAR info 2>&1) >output.txt || { echo "Info failed"; exit 1; }
txtmatch.py expected.txt output.txt || { echo "Output mismatch at line $LINENO"; exit 1; }

cat >expected.txt <<EOF
ERROR: The current snapshot has been deleted in the repository.
!Finished in .* seconds
EOF
(cd TestSession && $BOAR status -q 2>&1) >output.txt && { cat output.txt; echo "Status for deleted snapshot should fail"; exit 1; }
txtmatch.py expected.txt output.txt || { echo "Output mismatch at line $LINENO"; exit 1; }


echo "Checking contents"
(cd TestSession && $BOAR update -q) || { echo "Update failed"; exit 1; }


# All the files should still be as in the original workdir, except that
# wd_deleted.txt should be restored.
cat >workdir_updated_contents.txt <<EOF
repo_deleted.txt:original 3
repo_modified.txt:original 2
unchanged.txt:original 1
wd_deleted.txt:original 5
wd_modified.txt:wd locally modified
EOF
(cd TestSession && grep . *.txt) >workdir_after_update.txt || { echo "Grep failed"; exit 1; }
txtmatch.py workdir_updated_contents.txt workdir_after_update.txt || { echo "Unexpected workdir contents after update"; exit 1; }

cat >expected_workdir_status.txt <<EOF
A repo_deleted.txt
M repo_modified.txt
  unchanged.txt
  wd_deleted.txt
M wd_modified.txt
!Finished in .* seconds
EOF
(cd TestSession && $BOAR status -vq) >output.txt || { echo "Status failed"; exit 1; }
txtmatch.py expected_workdir_status.txt output.txt || { echo "Unexpected workdir status after update"; exit 1; }

(cd TestSession && $BOAR info | grep "Revision: 4") || { echo "Unexpected revision"; exit 1; }

exit 0 # All is well
