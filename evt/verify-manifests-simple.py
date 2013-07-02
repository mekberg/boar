#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2012 Mats Ekberg
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
The purpose of this tool is to provide a simple example on how to
independently verify the contents of a Boar repository by taking
advantage of manifest files.

This program demonstrates some useful mechanisms for automatically
accessing a repository through boar. It shows how to list sessions,
how to list files in a session and how to access files in a repository
by file name or by blob id. We can do these things by using the Boar
commands "sessions", "contents", and "cat". These commands are
guaranteed to give clean machine-readable output.

Note that for simplicity and speed, this tool will only check if all
the files are intact and accessible by their blob ids. It will not
detect deviations from the file structure described in the
manifest. As long as the files are intact, the file structure can
always be reconstructed by using the manifest.
"""

# It would easy to import a lot of boar modules here, but the whole
# point of an _external_ verification tool is that it should not rely
# on anything in the boar package.

import json
import re
import sys
import hashlib
import subprocess
import os
import re

boar_cmd = "boar"
if os.name == 'nt':
    boar_cmd = "boar.bat"

def is_md5sum(str):
    try:
        return re.match("^[a-f0-9]{32}$", str) != None    
    except TypeError:
        return False
    
def run_command(*cmdlist):
    """Execute a shell command and return the output. Raises an
    exception if the command failed for any reason."""
    process = subprocess.Popen(cmdlist, stdout=subprocess.PIPE)
    stdoutdata, stderrdata = process.communicate()
    status = process.wait()
    if status != 0:
        print stdoutdata
        raise Exception("Command '%s' failed with error %s" % 
                        (cmdlist, status))
    return stdoutdata

def verify_blob(repourl, expected_md5):
    """This function will stream the given blob from the repository
    and verify that the contents are as expected. If an error is
    detected, an AssertionError will be raised."""

    # As the expected checksum and blob id are the same thing, this is
    # easy. It would be even easier if we used run_command() here, but
    # then we would have problems when handling files larger than
    # available RAM, as that function returns the complete output of
    # the command..
    assert len(expected_md5) == 32, "Not a valid md5sum: %s" % expected_md5
    boar_process = subprocess.Popen([boar_cmd, "--repo", repourl, "cat", "--blob", expected_md5],
                                    stdout=subprocess.PIPE)
    summer = hashlib.md5()
    while True:
        data = boar_process.stdout.read(4096)
        if data == "":
            break
        summer.update(data)
    assert boar_process.wait() == 0, "Boar gave unexpected return code"
    assert summer.hexdigest() == expected_md5, "Expected: %s Got: %s" % (expected_md5, summer.hexdigest())

def verify_manifest_by_md5(repourl, manifest_md5):
    """This function will load the given manifest and then verify the
    checksum of every file specified within."""

    print "Verifying manifest with md5", manifest_md5

    # Use the --punycode flag and encoded arguments to avoid problems
    # on Windows with non-ascii chars in command arguments.
    manifest_contents = run_command(boar_cmd, "--repo", repourl, "cat", "-B", manifest_md5)

    # Let's verify that the checksum in the name of the manifest
    # is correct.
    md5summer = hashlib.md5()
    md5summer.update(manifest_contents)
    assert manifest_md5 == md5summer.hexdigest(), \
        "Manifest with id %s doesn't have the expected checksum." % manifest_md5

    manifest_contents = manifest_contents.decode("utf-8-sig")

    for line in manifest_contents.splitlines():
        md5, filename = line[0:32], line[34:]
        verify_blob(repourl, md5)
        print filename, "OK"
    

def verify_manifest_by_path(repourl, session_name, manifest_path):
    """This function will load the given manifest and then verify the
    checksum of every file specified within. If the manifest file has
    a md5 checksum in its filename, the manifest file itself will be
    verified against that checksum."""

    print "Verifying manifest", session_name + "/" + manifest_path

    # Use the --punycode flag and encoded arguments to avoid problems
    # on Windows with non-ascii chars in command arguments.
    manifest_contents = run_command(boar_cmd, "--repo", repourl, "cat", "--punycode",
                                    (session_name + "/" + manifest_path).encode("punycode"))
    
    m = re.match(".*-([a-z0-9]{32})\.md5$", manifest_path, flags=re.IGNORECASE)
    expected_manifest_md5 = m.group(1) if m else None

    if expected_manifest_md5:
        # Let's verify that the checksum in the name of the manifest
        # is correct.
        md5summer = hashlib.md5()
        md5summer.update(manifest_contents)
        assert expected_manifest_md5 == md5summer.hexdigest(), \
            "Manifest %s checksum didn't match contents" % (session_name + "/" + manifest_path)
        print "%s OK" % (session_name + "/" + manifest_path)

    manifest_contents = manifest_contents.decode("utf-8-sig")

    for line in manifest_contents.splitlines():
        md5, filename = line[0:32], line[34:]
        verify_blob(repourl, md5)
        print filename, "OK"

def is_manifest(filename):
    """Returns True if a filename looks like a manifest file that this
    program will understand."""
    m = re.match("(^|.*/)(manifest-md5\.txt|manifest-[a-z0-9]{32}\.md5)", 
                 filename, flags=re.IGNORECASE)
    return m != None

def main():
    args = sys.argv[1:]
    if len(args) < 2:
        print """Usage: verify-manifests-simple.py <repository> [<id | <session>/<manifest>, ...]

This is a demonstration program that verifies manifests within a boar
repository. The first argument must always be a valid boar repository
path or url. If no other arguments are given, it searches the
repository for manifest files, and then verifies that the manifests
are correct. Only the latest revision of every session is scanned.

If more arguments are given after the repository, they must indicate
existing manifests. You can identify the manifests by either a valid
boar blob id or by using the session path.

Example: If you have a session named "MySession" with a manifest under
the path "pictures/manifest.md5" with the blob id (md5sum)
d41d8cd98f00b204e9800998ecf8427e, you could verify this manifest by
using any one of the following commands:

Using the blob id:
  verify-manifests-simple.py /var/boarrepo d41d8cd98f00b204e9800998ecf8427e

Using the session path:
  verify-manifests-simple.py /var/boarrepo MySession/pictures/manifest.md5
"""
        return

    repourl = args[0]

    if "-A" in args:
        assert len(args) == 2, "-A cannot be combined with an explicit manifest list"
        session_names = json.loads(run_command(boar_cmd, "--repo", repourl, "sessions", "--json"))
        manifest_ids = []
        for session_name in session_names:
            # The "boar contents" command will dump a json-list containing
            # information about the session, including a list of all the
            # files. We are using the --punycode flag and encoded
            # arguments to avoid problems on Windows with non-ascii chars
            # in command arguments.
            session_contents = json.loads(run_command(boar_cmd, "--repo", repourl,
                                                    "contents", "--punycode", session_name.encode("punycode")))
            for fileinfo in session_contents['files']:
                if is_manifest(fileinfo['filename']):
                    print "Found manifest", "%s/%s" % (session_name, fileinfo['filename'])
                    manifest_ids.append("%s/%s" % (session_name, fileinfo['filename']))
    else:
        manifest_ids = args[1:]
    del args

    for manifest_id in manifest_ids:
        if is_md5sum(manifest_id):
            verify_manifest_by_md5(repourl, manifest_id)
        else:
            session_name, path = manifest_id.split("/", 1)
            verify_manifest_by_path(repourl, session_name, path)

if __name__ == "__main__":
    main()
