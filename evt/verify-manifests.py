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
import os
import re

from extboar import *
from optparse import OptionParser, OptionGroup

boar_cmd = "boar"
if os.name == 'nt':
    boar_cmd = "boar.bat"

def find_checksum(s):
    """Accepts a manifest-style filename and returns the embedded
    checksum string, or None if no such string could be found."""
    m = re.search(r"\b([a-z0-9]{32})\b", s, flags=re.IGNORECASE)
    md5 = m.group(1).lower() if m else None
    return md5

def verify_manifest(extrepo, manifest_contents, manifest_md5):    
    assert is_md5sum(manifest_md5) or manifest_md5 == None
    if manifest_md5:
        md5summer = hashlib.md5()
        md5summer.update(manifest_contents)
        assert manifest_md5 == md5summer.hexdigest(), \
            "Manifest checksum didn't match contents"
        print "Manifest integrity OK"
    manifest_contents = manifest_contents.decode("utf-8-sig")

    for line in manifest_contents.splitlines():
        md5, filename = line[0:32], line[34:]
        extrepo.verify_blob(md5)
        print filename, "OK"

def verify_manifest_by_md5(extrepo, manifest_md5):
    """This function will load the given manifest and then verify the
    checksum of every file specified within."""
    print "Verifying manifest with md5", manifest_md5
    manifest_contents = load_blob(extrepo.get_blob(manifest_md5))
    verify_manifest(extrepo, manifest_contents, manifest_md5)

def verify_manifest_by_spath(extrepo, session_path):
    """This function will load the given manifest and then verify the
    checksum of every file specified within. If the manifest file has
    a md5 checksum in its filename, the manifest file itself will be
    verified against that checksum."""

    print "Verifying manifest", session_path
    session_name, manifest_path = session_path.split("/", 1)

    manifest_contents = load_blob(extrepo.get_blob_by_path(session_name, manifest_path))
    expected_manifest_md5 = find_checksum(manifest_path)
    verify_manifest(extrepo, manifest_contents, expected_manifest_md5)

def verify_manifest_in_file(extrepo, file_path):
    expected_manifest_md5 = find_checksum(file_path)
    manifest_contents = open(file_path, "rb").read()
    verify_manifest(extrepo, manifest_contents, expected_manifest_md5)

def is_manifest(filename):
    """Returns True if a filename looks like a manifest file that this
    program will understand."""
    m = re.match("(^|.*/)(manifest-md5\.txt|manifest-[a-z0-9]{32}\.md5)", 
                 filename, flags=re.IGNORECASE)
    return m != None

def main():
    parser = OptionParser(usage="""Usage: 
  verify-manifests.py <repository> <flags> [<manifest specifier>, ...]

  This tool verifies md5sum-style manifests against a boar
  repository. The manifest(s) can themselves be fetched from the
  repostory, or given as ordinary files.

  The first non-flag argument must always be a boar repository path or
  URL.

  The source of the manifests must always be specified by giving one
  of the -F, -B and -S flags.

  The remaining non-flag arguments must consist of a list of manifest
  specifiers (or sent on stdin, if --stdin is used). The specifiers
  can be on different forms depending on the chosen source.

Examples: 
  If there is a repository in "/var/repo" with a session named
  "MySession" with a manifest under the path "pictures/manifest.md5"
  with the blob id (md5sum) d41d8cd98f00b204e9800998ecf8427e, we could
  verify this manifest by any of the following commands:

    verify-manifests.py /var/repo -B d41d8cd98f00b204e9800998ecf8427e
    verify-manifests.py /var/repo -S "MySession/pictures/manifest.md5" 

  If we have a manifest file stored in /home/me/pics-2012.md5, we can
  verify it with this line:

    verify-manifests.py /var/repo -F /home/me/pics-2012.md5""")

    group = OptionGroup(parser, "Manifest source")
    group.add_option("-F", "--files", dest = "file_specs", action="store_true",
                      help="Manifest specifiers are local file paths")
    group.add_option("-B", "--blobids", dest = "blobid_specs", action="store_true",
                      help="Manifest specifiers are blob ids")
    group.add_option("-S", "--session-paths", dest = "spath_specs", action="store_true",
                      help="Manifest specifiers are session paths")
    parser.add_option_group(group)

    parser.add_option("--stdin", dest = "stdin", action="store_true",
                      help="Read manifest specifiers from stdin instead of accepting them as arguments.")

    (options, args) = parser.parse_args()

    if not args:
        parser.print_help()
        sys.exit(1)

    if (options.file_specs, options.blobid_specs, options.spath_specs).count(True) != 1:
        parser.error("You must always specify exactly one specifier flag (-F, -B, -S)")

    repourl = args[0]

    if "--stdin" in args:
        assert len(args) == 2, "--stdin cannot be combined with any other manifest specifiers"
        manifest_ids = [line.rstrip('\r\n') for line in sys.stdin.readlines()]        
    else:
        manifest_ids = args[1:]

    if not manifest_ids:
        parser.error("You must always specify at least one manifest specifier")

    extrepo = ExtRepo(repourl)

    if options.blobid_specs:
        verifier = verify_manifest_by_md5
    elif options.file_specs:
        verifier = verify_manifest_in_file
    elif options.spath_specs:
        verifier = verify_manifest_by_spath
        
    for manifest_id in manifest_ids:
        verifier(extrepo, manifest_id)


if __name__ == "__main__":
    main()
