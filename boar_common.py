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

import os

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
    assert filename not in ("bloblist.json", "session.json", "session.md5"), "safe_delete prevented deletion of session data"
    assert not filename.endswith(".fingerprint"), "safe_delete prevented deletion of session fingerprint"
    assert not filename.endswith(".recipe"), "safe_delete prevented deletion of recipe data"
    os.remove(path)

def treecompare_bloblists(from_bloblist, to_bloblist):
    """Constructs and returns a TreeComparer instance using the
    filenames and md5sums found in the given bloblist entries."""
    def bloblist_to_dict(bloblist):
        cmpdict = {}
        for b in bloblist:
            cmpdict[b['filename']] = b['md5sum']
        return cmpdict

    from_dict = bloblist_to_dict(from_bloblist)
    to_dict = bloblist_to_dict(to_bloblist)
    return TreeComparer(from_dict, to_dict)
