#!/bin/bash

cat <<EOF

This is a very simple bare-bones Boar manifest verifier. It is
intended as a minimal example on how to begin to write your own
verifier. It is not tested and is likely to break with strange error
messages.

Usage: simple-verify-manifest.sh <repository> <manifest blob id>

EOF


REPO=$1
MANIFEST=$2
MANIFEST_FILE=`mktemp`

echo "Verifying manifest '$MANIFEST' in repo '$REPO'"

function verify_blob()
{
    expected_md5=$1
    actual_md5=$( boar --repo=$REPO cat -B $expected_md5 | md5sum - | cut -c 1-32 )
    if [[ "$expected_md5" == "$actual_md5" ]]; then
	echo "$expected_md5 OK"
	return 0;
    else
	echo "$expected_md5 ERROR"
	return 1;
    fi
}

# This line fetches the manifest from the repository. The awk part is
# for removing the unicode BOM if present (some checksum programs,
# esp. on windows, likes to add those.).
boar --repo=$REPO cat -B $MANIFEST | awk '{if(NR==1)sub(/^\xef\xbb\xbf/,"");print}' >$MANIFEST_FILE

for md5 in $( cut -c 1-32 $MANIFEST_FILE ) ; do
    verify_blob $md5 || { echo "ERROR WHILE VERIFYING MANIFEST"; exit 1; }
done
rm $MANIFEST_FILE

echo "Manifest verified OK"

