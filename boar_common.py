# -*- coding: utf-8 -*-

# Copyright 2011 Mats Ekberg
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

from __future__ import with_statement

import os, re

from common import *

from treecomp import TreeComparer

def safe_delete_file(path):
    """This function behaves like os.remove(), except for filenames
    that looks like they may be part of vital session data. If such a
    filename is given as argument, an AssertionError will be raised
    and the file will not be deleted."""
    path = os.path.normcase(path)
    filename = os.path.basename(path)
    assert not is_md5sum(filename), "safe_delete prevented deletion of blob"
    assert not is_recipe_filename(filename), "safe_delete prevented deletion of recipe"
    assert filename not in ("bloblist.json", "session.json", "session.md5"), "safe_delete prevented deletion of session data"
    assert not filename.endswith(".fingerprint"), "safe_delete prevented deletion of session fingerprint"
    os.remove(path)

def safe_delete_recipe(path):
    path = os.path.normcase(path)
    filename = os.path.basename(path)
    assert is_recipe_filename(filename), "safe_delete_recipe can only delete recipes"
    os.remove(path)

def safe_delete_blob(path):
    path = os.path.normcase(path)
    filename = os.path.basename(path)
    assert is_md5sum(filename), "safe_delete_recipe can only delete blobs"
    os.remove(path)

def unsafe_delete(path):
    os.remove(path)

def bloblist_to_dict(bloblist):
    """Returns the bloblist as a dict on the form filename ->
    blobinfo."""
    blobdict = {}
    for b in bloblist:
        blobdict[b['filename']] = b
    assert len(blobdict) == len(bloblist), "Duplicate filename in bloblist"
    return blobdict

def treecompare_bloblists(from_bloblist, to_bloblist):
    """Constructs and returns a TreeComparer instance using the
    filenames and md5sums found in the given bloblist entries."""
    def bloblist_to_dict(bloblist):
        cmpdict = {}
        for b in bloblist:
            cmpdict[b['filename']] = b['md5sum']
        assert len(cmpdict) == len(bloblist), "Duplicate filename in bloblist"
        return cmpdict

    from_dict = bloblist_to_dict(from_bloblist)
    to_dict = bloblist_to_dict(to_bloblist)
    return TreeComparer(from_dict, to_dict)

def bloblist_delta(from_bloblist, to_bloblist):
    """ Calculate a delta bloblist given two complete bloblists."""
    tc = treecompare_bloblists(from_bloblist, to_bloblist)
    to_dict = bloblist_to_dict(to_bloblist)
    delta = []
    for fn in tc.all_changed_filenames():
        if tc.is_deleted(fn):
            delta.append({"action": "remove", "filename": fn})
        else:
            delta.append(to_dict[fn])
    return delta

def apply_delta(bloblist, delta):
    """ Apply a delta bloblist to a original bloblist, yielding a
    resulting bloblist."""
    for b in bloblist:
        assert "action" not in b
    for d in delta:
        assert d.get("action", None) in (None, "remove")
    fns_to_delete = set([b['filename'] 
                         for b in delta
                         if b.get("action", None) == "remove"])
    new_and_modified_dict = bloblist_to_dict([b 
                                              for b in delta
                                              if "action" not in b])
    result = []
    for b in bloblist:
        if b['filename'] in fns_to_delete:
            continue
        elif b['filename'] in new_and_modified_dict:
            result.append(new_and_modified_dict[b['filename']])
            del new_and_modified_dict[b['filename']]
        else:
            result.append(b)
    result += new_and_modified_dict.values()
    return result

def invert_bloblist(bloblist):
    """ Returns a dictionary on the form md5sum -> [blobinfo,
    blobinfo, ...] """    
    result = {}
    for bi in bloblist:
        if bi['md5sum'] not in result:
            result[bi['md5sum']] = []
        result[bi['md5sum']].append(bi)
    return result


def sorted_bloblist(bloblist):
    def info_comp(x, y):
        return cmp(x['filename'], y['filename'])
    return sorted(bloblist, info_comp)

def parse_manifest_name(path):
    """Returns a tuple (lowercase hash name, hash). Both are None if
    the path is not a valid manifest filename."""
    m = re.match("(^|.*/)(manifest-([a-z0-9]+).txt|manifest-([a-z0-9]{32})\.md5|(manifest.md5))", path, flags=re.IGNORECASE)
    if not m:
        return None, None
    if m.group(5):
        return "md5", None
    if m.group(3):
        hashname = m.group(3).lower()
        return hashname, None
    hashname = "md5"
    manifest_hash = m.group(4).lower()
    return hashname, manifest_hash

assert parse_manifest_name("/tmp/manifest.md5") == ("md5", None)
assert parse_manifest_name("/tmp/manifest-d41d8cd98f00b204e9800998ecf8427e.md5") == ("md5", "d41d8cd98f00b204e9800998ecf8427e")
assert parse_manifest_name("/tmp/manifest-md5.txt") == ("md5", None)
assert parse_manifest_name("/tmp/manifest-sha256.txt") == ("sha256", None)
assert parse_manifest_name("/tmp/tjohej.txt") == (None, None)
assert parse_manifest_name("/tmp/tjohej.md5") == (None, None)

def is_recipe_filename(filename):
    filename_parts = filename.split(".")
    return len(filename_parts) == 2 \
        and filename_parts[1] == "recipe" \
        and is_md5sum(filename_parts[0])


class SimpleProgressPrinter:
    def __init__(self, output, label = "Processing"):
        self.last_t = 0
        self.start_t = time.time()
        self.active = False
        self.last_string = ""
        self.label = printable(label); del label
        self.symbols = list('-\\|/')
        self.output = output
        self.updatecounter = 0

        if os.getenv("BOAR_HIDE_PROGRESS") == "1":
            # Only print the label, do nothing else.
            self.output.write(self.label)
            self.output.write("\n")
            self.output = FakeFile()

    def _say(self, s):
        # self.output will point to /dev/null if quiet
        self.output.write(s)
        self.output.flush()

    def update(self, f):
        self.active = True
        self.updatecounter += 1
        now = time.time()
        symbol = self.symbols.pop(0)
        self.symbols.append(symbol)
        eraser = (" " * len(self.last_string)) + "\r"
        self.last_string = self.label + ": %s%% [%s]" % (round(100.0 * f, 1), symbol)
        self._say(eraser + self.last_string + "\r")
        #print self.last_string
        self.last_t = now

    def finished(self):
        if self.active:
            self._say(self.last_string[:-3] + "    " + "\n")
