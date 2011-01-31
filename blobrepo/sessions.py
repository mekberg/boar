#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright 2010 Mats Ekberg
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
import tempfile
import re
import sys
if sys.version_info >= (2, 6):
    import json
else:
    import simplejson as json
import copy

import repository
import shutil
import hashlib

from common import *

"""
The SessionWriter and SessionReader are together with Repository the
only classes that directly accesses the repository. 

A session consists of a set of blobs and a set of metadatas. The
metadatas are dictionaries. Some keywords are reserved by the
repository, and some are required to be set by the client. Any
keys/values not specified here are stored and provided as they are.

md5sum:   Set/overwritten by the session.
filename: Required by the session, set by the client.
change:   Required by the session when creating a derived session. Can 
          be one of the following: add, remove, replace

The sessioninfo object also is mostly filled by the client, but a few
keywords are reserved.

base_session: The revision id of the revision that this revision is
        based on. May be null in case of a non-incremental revision.


"""

class AddException(Exception):
    pass

def bloblist_to_dict(bloblist):
    d = {}
    for b in bloblist:
        d[b['filename']] = b
    return d

def bloblist_fingerprint(bloblist):
    """Returns a hexadecimal string that is unique for a set of
    files."""
    md5 = hashlib.md5()
    blobdict = bloblist_to_dict(bloblist)
    filenames = blobdict.keys()
    filenames.sort()
    sep = "!SEPARATOR!"
    for fn in filenames:
        md5.update(fn.encode("utf-8"))
        md5.update(sep)
        md5.update(blobdict[fn]['md5sum'])
        md5.update(sep)
    return md5.hexdigest()

class SessionWriter:
    def __init__(self, repo, base_session = None, session_id = None):
        self.repo = repo
        self.base_session = base_session
        self.session_path = None
        self.metadatas = {}
        # Summers for new blobs. { blobname: summer, ... }
        self.blob_checksummers = {}
        assert os.path.exists(self.repo.repopath)
        self.session_path = tempfile.mkdtemp( \
            prefix = "tmp_", 
            dir = os.path.join(self.repo.repopath, repository.TMP_DIR))         
        self.base_session_info = {}
        self.base_bloblist_dict = {}
        if self.base_session != None:
            self.base_session_info = self.repo.get_session(self.base_session).get_properties()['client_data']
            self.base_bloblist_dict = bloblist_to_dict(\
                self.repo.get_session(self.base_session).get_all_blob_infos())
        self.resulting_blobdict = self.base_bloblist_dict

        self.forced_session_id = None
        if session_id != None:
            self.forced_session_id = int(session_id)
            assert self.forced_session_id > 0

    def add_blob_data(self, blob_md5, fragment):
        """ Adds the given fragment to the end of the new blob with the given checksum."""
        assert is_md5sum(blob_md5)
        assert not self.repo.has_blob(blob_md5), "blob already exists"
        if not self.blob_checksummers.has_key(blob_md5):
            self.blob_checksummers[blob_md5] = hashlib.md5()
        summer = self.blob_checksummers[blob_md5]
        summer.update(fragment)
        fname = os.path.join(self.session_path, blob_md5)
        with open(fname, "ab") as f:
            f.write(fragment)

    def has_blob(self, csum):
        fname = os.path.join(self.session_path, csum)
        return os.path.exists(fname)

    def add(self, metadata):
        assert metadata.has_key('md5sum')
        assert metadata.has_key('filename')
        assert metadata['filename'].find("\\") == -1, \
            "Filenames must be in unix format"
        assert metadata['filename'].find("//") == -1, \
            "Filenames must be normalized. Was:" + metadata['filename']
        assert not metadata['filename'].startswith("/"), \
            "Filenames must not be absolute. Was:" + metadata['filename']
        assert not metadata['filename'].endswith("/"), \
            "Filenames must not end with a path separator. Was:" + metadata['filename']
        new_blob_filename = os.path.join(self.session_path, metadata['md5sum'])
        assert self.repo.has_blob(metadata['md5sum']) \
            or os.path.exists(new_blob_filename), "Tried to add blob info, but no such blob exists: "+new_blob_filename
        assert metadata['filename'] not in self.metadatas
        self.metadatas[metadata['filename']] = metadata
        self.resulting_blobdict[metadata['filename']] = metadata

    def remove(self, filename):
        assert self.base_session
        assert self.base_bloblist_dict.has_key(filename)
        metadata = {'filename': filename,
                    'action': 'remove'}
        self.metadatas[filename] = metadata
        del self.resulting_blobdict[metadata['filename']]

    def commitClone(self, session):
        other_bloblist = session.get_all_blob_infos()
        self.resulting_blobdict = bloblist_to_dict(other_bloblist)
        self.metadatas = bloblist_to_dict(session.get_raw_bloblist())
        self.base_session = session.properties.get("base_session", None)
        sessioninfo = session.properties.get("client_data")
        added_blobs = set()
        for metadata in self.metadatas.values():
            if not 'md5sum' in metadata:
                # Probably a deletion entry
                continue
            blobname = metadata['md5sum']
            assert session.repo.has_raw_blob(blobname), "Other repo does not appear to have the blob we need"+\
                "(Recipe? Cloning of recipes not yet supported)"
            if not self.repo.has_blob(blobname) and blobname not in added_blobs:
                size = session.repo.get_blob_size(blobname)
                offset = 0
                added_blobs.add(blobname)
                while offset < size:
                    data = session.repo.get_blob(blobname, offset, 1000000)
                    assert len(data) > 0
                    offset += len(data)
                    self.add_blob_data(blobname, data)
        return self.commit(sessioninfo)

    def commit(self, sessioninfo = {}):
        assert self.session_path != None
        for name, summer in self.blob_checksummers.items():
            assert name == summer.hexdigest(), "Corrupted blob found in new session. Commit aborted."
        fingerprint = bloblist_fingerprint(self.resulting_blobdict.values())
        metainfo = { 'base_session': self.base_session,
                     'fingerprint': fingerprint,
                     'client_data': sessioninfo}
        bloblist_filename = os.path.join(self.session_path, "bloblist.json")
        assert not os.path.exists(bloblist_filename)
        with open(bloblist_filename, "wb") as f:
            json.dump(self.metadatas.values(), f, indent = 4)

        session_filename = os.path.join(self.session_path, "session.json")
        assert not os.path.exists(session_filename)
        with open(session_filename, "wb") as f:
            json.dump(metainfo, f, indent = 4)

        md5_filename = os.path.join(self.session_path, "session.md5")
        with open(md5_filename, "wb") as f:
            f.write(md5sum_file(bloblist_filename) + " *bloblist.json\n")
            f.write(md5sum_file(session_filename) + " *session.json\n")
        
        fingerprint_marker = os.path.join(self.session_path, fingerprint + ".fingerprint")
        with open(fingerprint_marker, "wb") as f:
            pass

        assert not self.repo.get_queued_session_id()
        if self.forced_session_id: 
            session_id = self.forced_session_id
        else:
            session_id = self.repo.find_next_session_id()
        assert session_id > 0
        assert session_id not in self.repo.get_all_sessions()
        queue_dir = self.repo.get_queue_path(str(session_id))
        shutil.move(self.session_path, queue_dir)
        self.repo.process_queue()
        return session_id


class SessionReader:
    def __init__(self, repo, session_path):
        assert session_path, "Session path must be given"
        self.path = session_path
        self.repo = repo
        assert os.path.exists(self.path), "No such session path:" + self.path

        self.bloblist = None
        self.verified = False

        path = os.path.join(self.path, "session.json")
        with open(path, "rb") as f:
            self.properties = json.load(f)

    def get_properties(self):
        return copy.copy(self.properties)

    def get_fingerprint(self):
        return self.properties['fingerprint']

    def verify(self):
        if self.verified:
            return
        bloblist = self.get_all_blob_infos()
        expected_fingerprint = bloblist_fingerprint(bloblist)
        assert self.properties['fingerprint'] == expected_fingerprint
        contents = os.listdir(self.path)
        assert set(contents) == \
            set([expected_fingerprint+".fingerprint",\
                     "session.json", "bloblist.json", "session.md5"]), \
                     "Missing or unexpected files in session dir: "+self.path
        for blobinfo in bloblist:
            assert repo.has_blob(blobinfo['md5sum'])
        self.verified = True

    def get_raw_bloblist(self):
        self.__load_bloblist()
        return self.bloblist

    def __load_bloblist(self):
        if self.bloblist == None:
            path = os.path.join(self.path, "bloblist.json")
            with open(path, "rb") as f:
                self.bloblist = json.load(f)

    def get_all_blob_infos(self):
        self.__load_bloblist()
        seen = set()
        for blobinfo in self.bloblist:
            assert blobinfo['filename'] not in seen, \
                "Internal error - duplicate file entry in a single session"
            seen.add(blobinfo['filename'])
            if blobinfo.get("action", None) == "remove":
                continue
            yield copy.copy(blobinfo)
        base_session_id = self.properties.get("base_session", None)
        if base_session_id:
            base_session_reader = self.repo.get_session(base_session_id)
            for info in base_session_reader.get_all_blob_infos():
                if info['filename'] not in seen:
                    # Later entries overrides earlier ones
                    yield info
