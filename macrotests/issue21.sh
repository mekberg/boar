#!/bin/bash

# Test option to ignore errors during import

boar=~+/`dirname $0`/../boar
testdir="/tmp/issue21_tmp$$"

mkdir $testdir || exit 1
cd $testdir || exit 1
mkdir workdir || exit 1
echo >workdir/file.txt || exit 1
echo >workdir/file_unreadable.txt || exit 1
chmod a-r workdir/file_unreadable.txt || exit 1
$boar mkrepo TESTREPO || exit 1
$boar --repo=TESTREPO mksession "Test" || exit 1
$boar --repo=TESTREPO import workdir "Test/workdir" && { echo "Import of non-readable file succeeded - should fail"; exit 1; }
$boar --repo=TESTREPO import --ignore-errors workdir "Test/workdir" || { echo "Import failed even though --ignore-errors was given"; exit 1; }
rm -r $testdir || exit 1
echo "Test succeeded"
