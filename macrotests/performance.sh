#!/bin/bash

boar=~+/`dirname $0`/../boar
macrotests=~+/`dirname $0`/
testdir="/tmp/boarperf_tmp$$"


# Test for simple unreadable file
mkdir $testdir || exit 1
cd $testdir || exit 1
mkdir workdir || exit 1
$macrotests/randtree.py workdir 5000 1
$boar mkrepo TESTREPO || exit 1
$boar --repo=TESTREPO mksession "Test" || exit 1
sync
echo "Test tree created. Importing..."
time $boar --repo=TESTREPO import -w workdir "Test/workdir" || { echo "Import of benchmark tree failed"; exit 1; }
time (cd workdir; $boar --repo=TESTREPO status;) || { echo "Status command failed"; exit 1; }
du -b workdir
rm -r $testdir || exit 1
