#
# Issue 105: Too restrictive permissions on session folders
#

# Just make sure that everything works as expected before we start the
# actual test
(umask 0000 && touch test.txt) || exit 1
if [ `stat -c '%A' test.txt` != "-rw-rw-rw-" ]; then
    echo "Unexpected permissions"
    exit 1
fi

# Test a very permissive mask
TESTREPO=TESTREPO1
(umask 000 && $BOAR mkrepo $TESTREPO) || exit 1
(umask 000 && $BOAR --repo=$TESTREPO mksession "TestSession") || exit 1

ls -ld $TESTREPO/sessions/1 || exit 1

if [ `stat -c '%A' $TESTREPO/sessions/1` != "drwxrwxrwx" ]; then
    echo "Wrong permissions on session folder for umask 000"
    exit 1
fi

TESTREPO=TESTREPO2

# Test the common case of others having only reading rights
(umask 022 && $BOAR mkrepo $TESTREPO) || exit 1
(umask 022 && $BOAR --repo=$TESTREPO mksession "TestSession") || exit 1

ls -ld $TESTREPO/sessions/1 || exit 1

if [ `stat -c '%A' $TESTREPO/sessions/1` != "drwxr-xr-x" ]; then
    echo "Wrong permissions on session folder for umask 022"
    exit 1
fi

TESTREPO=TESTREPO3

# Test a restrictive mask
(umask 077 && $BOAR mkrepo $TESTREPO) || exit 1
(umask 077 && $BOAR --repo=$TESTREPO mksession "TestSession") || exit 1

ls -ld $TESTREPO/sessions/1 || exit 1

if [ `stat -c '%A' $TESTREPO/sessions/1` != "drwx------" ]; then
    echo "Wrong permissions on session folder for umask 077"
    exit 1
fi


