#!/bin/bash

# Test option to ignore errors during import

# Test for simple unreadable file
mkdir workdir || exit 1
echo "file1" >workdir/file.txt || exit 1
echo "file2" >workdir/file_unreadable.txt || exit 1
chmod a-r workdir/file_unreadable.txt || exit 1
$BOAR mkrepo TESTREPO || exit 1
$BOAR --repo=TESTREPO mksession "Test" || exit 1
$BOAR --repo=TESTREPO import -W workdir "Test/workdir" && { echo "Import of non-readable file succeeded - should fail"; exit 1; }
$BOAR --repo=TESTREPO import -W --ignore-errors workdir "Test/workdir" || { echo "Import failed even though --ignore-errors was given"; exit 1; }
chmod -R u+r workdir || exit 1
rm -r workdir || exit 1
rm -r TESTREPO || exit 1
echo "Test part 1 succeeded"

# Test for file that is readable during changes scan, but unreadable during actual checkin
cat >make_unreadable_at_commit.py <<"EOF"
def modify_fn(fn):
    def newfn(*args, **kwargs):
        import os
        os.chmod("workdir/file_unreadable.txt", 0000)
        try:
            return fn(*args, **kwargs)
        finally:
            os.chmod("workdir/file_unreadable.txt", 0744)
    return newfn

workdir.check_in_file = modify_fn(workdir.check_in_file)
EOF
mkdir workdir || exit 1
echo "file1" >workdir/file.txt || exit 1
echo "file2" >workdir/file_unreadable.txt || exit 1
$BOAR mkrepo TESTREPO || exit 1
$BOAR --repo=TESTREPO mksession "Test" || exit 1
$BOAR --EXEC make_unreadable_at_commit.py --repo=TESTREPO import -W workdir "Test/workdir" && { echo "Import of non-readable file succeeded - should fail"; exit 1; }
$BOAR --EXEC make_unreadable_at_commit.py --repo=TESTREPO import -W --ignore-errors workdir "Test/workdir" || { echo "Import failed even though --ignore-errors was given"; exit 1; }
chmod -R u+r workdir || exit 1
echo "Test part 2 succeeded"

### This section is disabled for now
# # Repeat test for unreadable directory
# mkdir $testdir || exit 1
# cd $testdir || exit 1
# mkdir workdir || exit 1
# mkdir workdir/unreadable_dir || exit 1
# echo "file1" >workdir/file.txt || exit 1
# echo "file2" >workdir/unreadable_dir/file.txt || exit 1
# chmod a-r workdir/unreadable_dir || exit 1
# $BOAR mkrepo TESTREPO || exit 1
# $BOAR --repo=TESTREPO mksession "Test" || exit 1
# $BOAR --repo=TESTREPO import workdir "Test/workdir" && { echo "Import of non-readable directory succeeded - should fail"; exit 1; }
# $BOAR --repo=TESTREPO import --ignore-errors workdir "Test/workdir" || { echo "Import of unreadable dir failed even though --ignore-errors was given"; exit 1; }
# chmod -R u+r workdir || exit 1
# rm -r $testdir || exit 1
# echo "Test part 2 succeeded"

