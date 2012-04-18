# Test that it compiles and some very basic operations. Convenient to
# have as the very first test.

$BOAR --version || exit 1
$BOAR mkrepo TESTREPO || exit 1
$BOAR --repo=TESTREPO ls || exit 1

true
