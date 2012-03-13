#!/bin/bash
# Test co and update for offset workdirs. 

mkdir workdir || exit 1
echo >workdir/file1.txt || exit 1
mkdir workdir_longer || exit 1
echo >workdir_longer/file2.txt || exit 1
$BOAR mkrepo TESTREPO || exit 1
$BOAR --repo=TESTREPO mksession "a" || exit 1
$BOAR --repo=TESTREPO import -w workdir "a/workdir" || exit 1
$BOAR --repo=TESTREPO import -w workdir_longer "a/workdir_longer" || exit 1
cd workdir_longer || exit 1
echo hello > file2.txt || exit 1
$BOAR ci || exit 1
cd .. || exit 1
$BOAR --repo=TESTREPO co a/workdir a || exit 1
cd workdir || exit 1
$BOAR update || exit 1


