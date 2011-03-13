#!/bin/bash

# Test co and update for offset workdirs. 

boar="`pwd`/../boar"
testdir="/tmp/issue12_tmp$$"

mkdir $testdir || exit 1
cd $testdir || exit 1
mkdir workdir || exit 1
echo >workdir/file1.txt || exit 1
mkdir workdir_longer || exit 1
echo >workdir_longer/file2.txt || exit 1
$boar mkrepo TESTREPO || exit 1
$boar --repo=TESTREPO mksession "a" || exit 1
$boar --repo=TESTREPO import -w workdir "a/workdir" || exit 1
$boar --repo=TESTREPO import -w workdir_longer "a/workdir_longer" || exit 1
cd workdir_longer || exit 1
echo hello > file2.txt || exit 1
$boar ci || exit 1
cd .. || exit 1
$boar --repo=TESTREPO co a/workdir || exit 1
cd workdir || exit 1
$boar update || exit 1
cd ../.. || exit 1
rm -r $testdir || exit 1
