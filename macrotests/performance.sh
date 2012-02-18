#!/bin/bash

#for i in {1..10}; do ./performance.sh >>performance_log.txt; done

if test -z "$TMP"; then
    echo "You must set \$TMP before running this script"
    exit 1
fi
boar=~+/`dirname $0`/../boar
macrotests=~+/`dirname $0`/
testdir="$TMP/boarperf_tmp$$"
test_tree=$1

# randtree.py test_tree 10 1000 1000000000 || exit 1

mkdir $testdir || exit 1
cd $testdir || exit 1
$boar mkrepo TESTREPO >/dev/null || exit 1
$boar --repo=TESTREPO mksession "Test" >/dev/null || exit 1
sync

t1=`date +"%s"`
$boar --repo=TESTREPO import $test_tree Test >/dev/null|| { echo "Import of benchmark tree failed"; exit 1; }
sync
t2=`date +"%s"`
echo "Time for import:" $[ $t2 - $t1 ] "seconds"


t1=`date +"%s"`
$boar --repo=TESTREPO co Test >/dev/null|| { echo "Co of benchmark tree failed"; exit 1; }
sync
t2=`date +"%s"`
echo "Time for co:" $[ $t2 - $t1 ] "seconds"


rm -r $testdir || exit 1
