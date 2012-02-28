# Test that the verify command detects corruptions
set -e

$BOAR mkrepo TESTREPO || exit 1
$BOAR mksession --repo=TESTREPO TestSession || exit 1
$BOAR co --repo=TESTREPO TestSession || exit 1

echo "Rev 2" >TestSession/r2.txt || exit 1
(cd TestSession && $BOAR ci -q) || exit 1

rm TestSession/r2.txt || exit 1
echo "Rev 3" >TestSession/r3.txt || exit 1
(cd TestSession && $BOAR ci -q) || exit 1

rm TestSession/r3.txt || exit 1
echo "Rev 4" >TestSession/r4.txt || exit 1
(cd TestSession && $BOAR ci -q) || exit 1

$BOAR verify --repo=TESTREPO || { echo "Repo failed initial verification"; exit 1; }

{ # Test missing blob
RUT=REPO_missing_blob
cp -a TESTREPO $RUT || exit 1
rm $RUT/blobs/4b/4b5c8990f5e8836e8f69bf5b1f19da9e || exit 1
$BOAR verify --repo=$RUT && { echo "Error in $RUT was not detected"; exit 1; }
$BOAR verify --repo=$RUT | grep "REPO CORRUPTION: Snapshot 3 is missing blob 4b5c8990f5e8836e8f69bf5b1f19da9e" || \
    { echo "$RUT gave unexpected error message"; exit 1; }
}

{ # Test corrupted blob
RUT=REPO_corrupted_blob
cp -a TESTREPO $RUT || exit 1
echo "Williamspäron" >$RUT/blobs/4b/4b5c8990f5e8836e8f69bf5b1f19da9e || exit 1
$BOAR verify --repo=$RUT && { echo "Error in $RUT was not detected"; exit 1; }
$BOAR verify --repo=$RUT | grep "REPO CORRUPTION: Blob corrupted: 4b5c8990f5e8836e8f69bf5b1f19da9e" || \
    { echo "$RUT gave unexpected error message"; exit 1; }
}

{ # Test snapshot duplicate fingerprint 
RUT=REPO_duplicate_fingerprint
cp -a TESTREPO $RUT || exit 1
touch $RUT/sessions/2/4b5c8990f5e8836e8f69bf5b1f19da9e.fingerprint || exit 1
$BOAR verify --repo=$RUT && { echo "Error in $RUT was not detected"; exit 1; }
$BOAR verify --repo=$RUT | grep "REPO CORRUPTION: Session 2 contains multiple fingerprint files" || \
    { echo "$RUT gave unexpected error message"; exit 1; }
}

{ # Test snapshot missing fingerprint 
RUT=REPO_missing_fingerprint
cp -a TESTREPO $RUT || exit 1
rm $RUT/sessions/2/8061e73301587d92fdca155181c92961.fingerprint || exit 1
$BOAR verify --repo=$RUT && { echo "Error in $RUT was not detected"; exit 1; }
$BOAR verify --repo=$RUT | grep "REPO CORRUPTION: Session 2 is missing the fingerprint file" || \
    { echo "$RUT gave unexpected error message"; exit 1; }
}

{ # Test snapshot wrong fingerprint 
RUT=REPO_wrong_fingerprint
cp -a TESTREPO $RUT || exit 1
rm $RUT/sessions/2/8061e73301587d92fdca155181c92961.fingerprint || exit 1
touch $RUT/sessions/2/4b5c8990f5e8836e8f69bf5b1f19da9e.fingerprint || exit 1
$BOAR verify --repo=$RUT && { echo "Error in $RUT was not detected"; exit 1; }
$BOAR verify --repo=$RUT | grep "REPO CORRUPTION: Session 2 has an invalid fingerprint file" || \
    { echo "$RUT gave unexpected error message"; exit 1; }
}

{ # Test snapshot session.json integrity
RUT=REPO_modified_session.json
cp -a TESTREPO $RUT || exit 1
echo " " >> $RUT/sessions/2/session.json || exit 1
$BOAR verify --repo=$RUT && { echo "Error in $RUT was not detected"; exit 1; }
$BOAR verify --repo=$RUT | grep "REPO CORRUPTION: Internal file session.json for snapshot 2 does not match expected checksum" || \
    { echo "$RUT gave unexpected error message"; exit 1; }
}

{ # Test snapshot bloblist.json integrity
RUT=REPO_modified_bloblist.json
cp -a TESTREPO $RUT || exit 1
echo " " >> $RUT/sessions/2/bloblist.json || exit 1
$BOAR verify --repo=$RUT && { echo "Error in $RUT was not detected"; exit 1; }
$BOAR verify --repo=$RUT | grep "REPO CORRUPTION: Internal file bloblist.json for snapshot 2 does not match expected checksum" || \
    { echo "$RUT gave unexpected error message"; exit 1; }
}

{ # Test missing snapshot
RUT=REPO_missing_snapshot
cp -a TESTREPO $RUT || exit 1
rm -r $RUT/sessions/2 || exit 1
$BOAR verify --repo=$RUT && { echo "Error in $RUT was not detected"; exit 1; }
$BOAR verify --repo=$RUT | grep "REPO CORRUPTION: Required base snapshot 2 is missing" || \
    { echo "$RUT gave unexpected error message"; exit 1; }
}

{ # Test modified bloblist (session.md5 assumed valid, perhaps after
  # manual modification or RAM error while writing)
RUT=REPO_modified_bloblist
cp -a TESTREPO $RUT || exit 1
sed -e 's/"filename": "r2.txt"/"filename": "r2_modified.txt"/g' -i $RUT/sessions/2/bloblist.json || exit 1
(cd $RUT/sessions/2 && md5sum *.json >session.md5) || exit 1
$BOAR verify --repo=$RUT && { echo "Error in $RUT was not detected"; exit 1; }
$BOAR verify --repo=$RUT | grep "REPO CORRUPTION: Fingerprint didn't match for snapshot 2" || \
    { echo "$RUT gave unexpected error message"; exit 1; }
}

{ # Test modified bloblist (session.md5 assumed valid, perhaps after
  # manual modification or RAM error while writing)
RUT=REPO_corrupted_bloblist
cp -a TESTREPO $RUT || exit 1
echo "Certainly not a valid json document" > $RUT/sessions/2/bloblist.json || exit 1
(cd $RUT/sessions/2 && md5sum *.json >session.md5) || exit 1
$BOAR verify --repo=$RUT && { echo "Error in $RUT was not detected"; exit 1; }
$BOAR verify --repo=$RUT | grep "REPO CORRUPTION: Bloblist for snapshot 2 is mangled" || \
    { echo "$RUT gave unexpected error message"; exit 1; }
}

true

