# Test the locate command with --json and --all-sessions flags

export REPO_PATH=`pwd`/TESTREPO
$BOAR mkrepo $REPO_PATH || exit 1

# Create first session with some files
$BOAR mksession --repo=$REPO_PATH Session1 || exit 1
$BOAR co Session1 || exit 1

echo "File in session 1" >Session1/file1.txt || exit 1
echo "Shared file" >Session1/shared.txt || exit 1
mkdir Session1/subdir || exit 1
echo "File in subdir" >Session1/subdir/file2.txt || exit 1
(cd Session1 && $BOAR ci -q) || exit 1

# Create second session with different files
$BOAR mksession --repo=$REPO_PATH Session2 || exit 1
$BOAR co Session2 || exit 1

echo "File in session 2" >Session2/file3.txt || exit 1
echo "Shared file" >Session2/shared.txt || exit 1
echo "Another file" >Session2/another.txt || exit 1
(cd Session2 && $BOAR ci -q) || exit 1

# Create third session
$BOAR mksession --repo=$REPO_PATH Session3 || exit 1
$BOAR co Session3 || exit 1

echo "File in session 3" >Session3/file4.txt || exit 1
(cd Session3 && $BOAR ci -q) || exit 1

# Test 1: Basic locate command (existing functionality)
echo "--- Test basic locate"
echo "File in session 1" >test_file1.txt || exit 1
$BOAR locate Session1 test_file1.txt | grep "OK: " || { echo "Failed to locate existing file"; exit 1; }

# Test 2: Locate missing file
echo "--- Test locate missing file"
echo "Not in repo" >missing_file.txt || exit 1
$BOAR locate Session1 missing_file.txt | grep "Missing: " || { echo "Failed to identify missing file"; exit 1; }

# Test 3: JSON output (now implies --all-sessions)
echo "--- Test JSON output (implies --all-sessions)"
echo "File in session 1" >test_file1.txt || exit 1
echo "Not in repo" >missing_file.txt || exit 1
$BOAR locate --json test_file1.txt missing_file.txt >json_output.txt || exit 1

# Verify JSON is valid and has required keys
python3 <<EOF || exit 1
import json
import sys

with open('json_output.txt', 'r') as f:
    data = json.load(f)

# Check that data is a list
if not isinstance(data, list):
    print("ERROR: JSON output should be a list")
    sys.exit(1)

if len(data) != 2:
    print("ERROR: Expected 2 entries, got", len(data))
    sys.exit(1)

# Find the existing and missing entries
existing_entries = [e for e in data if e.get('existing')]
missing_entries = [e for e in data if not e.get('existing')]

if len(existing_entries) != 1:
    print("ERROR: Expected 1 existing file, got", len(existing_entries))
    sys.exit(1)

if len(missing_entries) != 1:
    print("ERROR: Expected 1 missing file, got", len(missing_entries))
    sys.exit(1)

# Check existing entry structure
existing_entry = existing_entries[0]
if 'filename' not in existing_entry or 'md5' not in existing_entry or 'sessions' not in existing_entry:
    print("ERROR: Existing entry missing required fields")
    print(existing_entry)
    sys.exit(1)

sessions_dict = existing_entry['sessions']
if 'Session1' not in sessions_dict:
    print("ERROR: Expected Session1 in sessions")
    sys.exit(1)

repo_paths = sessions_dict['Session1']
if not isinstance(repo_paths, list):
    print("ERROR: repo_paths should be a list")
    sys.exit(1)

if len(repo_paths) != 1:
    print("ERROR: Expected 1 repo path, got", len(repo_paths))
    sys.exit(1)

# Check missing entry structure
missing_entry = missing_entries[0]
if 'filename' not in missing_entry or 'sessions' not in missing_entry or 'md5' not in missing_entry:
    print("ERROR: Missing entry missing required fields")
    print(missing_entry)
    sys.exit(1)

# Check that missing file has empty sessions dict
if missing_entry['sessions'] != {}:
    print("ERROR: Missing file should have empty sessions dict")
    print(missing_entry)
    sys.exit(1)

print("JSON output validation passed")
EOF

# Test 4: All sessions flag without JSON
echo "--- Test --all-sessions flag"
echo "Shared file" >shared.txt || exit 1
$BOAR locate --all-sessions shared.txt | grep "OK: " || { echo "Failed to locate file with --all-sessions"; exit 1; }
$BOAR locate --all-sessions shared.txt | grep "\[Session1\]" || { echo "Session1 not found in output"; exit 1; }
$BOAR locate --all-sessions shared.txt | grep "\[Session2\]" || { echo "Session2 not found in output"; exit 1; }
$BOAR locate --all-sessions shared.txt | grep "\[Session3\]" && { echo "Session3 should not be in output"; exit 1; }

# Test 5: JSON output searches all sessions
echo "--- Test JSON searches all sessions"
echo "File in session 1" >test_file1.txt || exit 1
echo "Shared file" >shared.txt || exit 1
echo "Not in repo" >missing_file.txt || exit 1
$BOAR locate --json test_file1.txt shared.txt missing_file.txt >json_all_output.txt || exit 1

python3 <<EOF || exit 1
import json
import sys

with open('json_all_output.txt', 'r') as f:
    data = json.load(f)

# Check that data is a list
if not isinstance(data, list):
    print("ERROR: JSON output should be a list")
    sys.exit(1)

if len(data) != 3:
    print("ERROR: Expected 3 entries, got", len(data))
    sys.exit(1)

# Find existing and missing entries
existing_entries = [e for e in data if e.get('existing')]
missing_entries = [e for e in data if not e.get('existing')]

if len(existing_entries) != 2:
    print("ERROR: Expected 2 existing files, got", len(existing_entries))
    sys.exit(1)

if len(missing_entries) != 1:
    print("ERROR: Expected 1 missing file, got", len(missing_entries))
    sys.exit(1)

# Find shared.txt in the existing files
shared_txt_found = False
for entry in existing_entries:
    if 'shared.txt' in entry['filename']:
        shared_txt_found = True
        
        if 'md5' not in entry or 'sessions' not in entry:
            print("ERROR: entry should have md5 and sessions keys")
            sys.exit(1)
        
        sessions_dict = entry['sessions']
        
        # Check that both Session1 and Session2 are present
        if 'Session1' not in sessions_dict or 'Session2' not in sessions_dict:
            print("ERROR: shared.txt should be in both Session1 and Session2")
            print("Sessions found:", list(sessions_dict.keys()))
            sys.exit(1)
        
        # Check that each session has a list of paths
        for session, paths in sessions_dict.items():
            if not isinstance(paths, list):
                print("ERROR: paths should be a list for session", session)
                sys.exit(1)

if not shared_txt_found:
    print("ERROR: shared.txt not found in existing files")
    sys.exit(1)

# Check missing file
missing_entry = missing_entries[0]
if 'md5' not in missing_entry or 'sessions' not in missing_entry:
    print("ERROR: Missing entry should have md5 and sessions")
    sys.exit(1)

if missing_entry['sessions'] != {}:
    print("ERROR: Missing file should have empty sessions dict")
    print(missing_entry)
    sys.exit(1)

print("JSON all-sessions output validation passed")
EOF

# Test 6: JSON with directory
echo "--- Test JSON with directory"
mkdir test_locate_dir || exit 1
echo "File in session 1" >test_locate_dir/file1.txt || exit 1
echo "File in session 2" >test_locate_dir/file3.txt || exit 1
echo "Not in any session" >test_locate_dir/missing.txt || exit 1

$BOAR locate --json test_locate_dir >json_dir_output.txt || exit 1

python3 <<EOF || exit 1
import json
import sys

with open('json_dir_output.txt', 'r') as f:
    data = json.load(f)

# Check that data is a list
if not isinstance(data, list):
    print("ERROR: JSON output should be a list")
    sys.exit(1)

# Find existing and missing entries
existing_entries = [e for e in data if e.get('existing')]
missing_entries = [e for e in data if not e.get('existing')]

# Should have found files in Session1 and Session2
found_sessions = set()
for entry in existing_entries:
    if 'md5' not in entry or 'sessions' not in entry:
        print("ERROR: entry should have md5 and sessions keys")
        sys.exit(1)
    for session in entry['sessions'].keys():
        found_sessions.add(session)

if 'Session1' not in found_sessions:
    print("ERROR: Should have found files in Session1")
    sys.exit(1)

if 'Session2' not in found_sessions:
    print("ERROR: Should have found files in Session2")
    sys.exit(1)

# Should have one missing file
if len(missing_entries) != 1:
    print("ERROR: Expected 1 missing file, got", len(missing_entries))
    sys.exit(1)

print("Directory locate validation passed")
EOF

# Test 7: Error handling - non-existent session
echo "--- Test error handling"
echo "Some file" >test.txt || exit 1
$BOAR locate --repo=$REPO_PATH NonExistentSession test.txt 2>&1 | grep "No such session" || {
    echo "Should error on non-existent session"; exit 1;
}

# Test that --json with session name is an error (when session name doesn't exist as a directory)
echo "--- Test --json with session name is an error"
$BOAR mksession --repo=$REPO_PATH SessionNoDir || exit 1
echo "File in session 1" >test_file1.txt || exit 1
$BOAR locate --json SessionNoDir test_file1.txt 2>&1 | grep -E "Cannot specify session name|implies" || {
    echo "Should error when session name provided with --json"; exit 1;
}

# Test 8: Verify that single argument is treated as session name
# (with current directory as default file location)
$BOAR locate --repo=$REPO_PATH test.txt 2>&1 | grep "No such session" || {
    echo "Single argument should be treated as session name"; exit 1;
}

echo "All locate tests passed"
true
