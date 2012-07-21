echo --- Test basic command line behaviour

$BOAR && { echo "Missing command should give an error code"; exit 1; }
($BOAR | grep "Commands:" >/dev/null ) || { echo "Missing subcommand did not yield help"; exit 1; }
($BOAR --help | grep "Commands:" >/dev/null ) || { echo "No subcommand did not yield help"; exit 1; }
$BOAR >/dev/null && { echo "No subcommand should cause an exit error code"; exit 1; }
$BOAR nonexisting_cmd >/dev/null && { echo "Non-existing subcommand should cause an exit error code"; exit 1; }

# Issue 27 - Exception when giving only --repo command line option
$BOAR --repo=/nonexisting/ >no_cmd_output.txt 2>&1 && { echo "No subcommand with --repo should cause an exit error code"; exit 1; }
grep "Usage: boar" no_cmd_output.txt || { 
    cat no_cmd_output.txt; echo "No subcommand with --repo gave unexpected error message"; exit 1; }

echo --- Test --help flag
for subcmd in cat ci clone co contents diffrepo getprop info import list locate log ls mkrepo mksession setprop status update verify; do
    echo Testing $subcmd --help
    ( REPO_PATH="" $BOAR $subcmd --help | grep "Usage:" >/dev/null ) || \
	{ echo "Subcommand '$subcmd' did not give a help message with --help flag"; exit 1; }
done

echo --- Test --version flag
$BOAR --version || { echo "--version should not cause an error code"; exit 1; }
($BOAR --version | grep "Copyright" >/dev/null ) || { echo "--version did not give expected output"; exit 1; }
$BOAR --version mkrepo ErrRepo1 && { echo "--version accepted extra commands"; exit 1; }
$BOAR mkrepo ErrRepo2 --version && { echo "--version accepted extra commands"; exit 1; }

echo --- Test nice error message when executing workdir commands in a non-workdir
mkdir nonrepo
(cd nonrepo; $BOAR status 2>&1 | grep "This directory is not a boar workdir" ) || { echo "Non-workdir status caused unexpected error message"; exit 1; }
(cd nonrepo; $BOAR ci 2>&1 | grep "This directory is not a boar workdir" ) || { echo "Non-workdir ci caused unexpected error message"; exit 1; }
(cd nonrepo; $BOAR info 2>&1 | grep "This directory is not a boar workdir" ) || { echo "Non-workdir info caused unexpected error message"; exit 1; }
(cd nonrepo; $BOAR update 2>&1 | grep "This directory is not a boar workdir" ) || { echo "Non-workdir update caused unexpected error message"; exit 1; }

echo --- Test that asserts disabling is disabled
python -O $BOAR --version && exit 1

true
