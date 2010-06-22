#!/usr/bin/python
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
        md5.update(fn)
        md5.update(sep)
        md5.update(blobdict[fn]['md5sum'])
        md5.update(sep)
    return md5.hexdigest()

class SessionWriter:
    def __init__(self, repo, base_session = None):
        self.repo = repo
        self.base_session = base_session
        self.session_path = None
        self.metadatas = {}
        assert os.path.exists(self.repo.repopath)
        self.session_path = tempfile.mkdtemp( \
            prefix = "tmp_", 
            dir = os.path.join(self.repo.repopath, repository.TMP_DIR))         
        self.base_session_info = {}
        self.base_bloblist_dict = {}
        if self.base_session != None:
            self.base_session_info = self.repo.get_session(self.base_session).session_info
            self.base_bloblist_dict = bloblist_to_dict(\
                self.repo.get_session(self.base_session).get_all_blob_infos())
        self.resulting_blobdict = self.base_bloblist_dict

    def add(self, data, metadata):
        assert data != None
        assert metadata != None
        assert self.session_path != None
        assert metadata.has_key('md5sum')
        assert metadata.has_key('filename')
        sum = md5sum(data)
        if sum != metadata['md5sum']:
            raise AddException("Calculated checksum did not match client provided checksum")
        fname = os.path.join(self.session_path, sum)
        existing_blob = self.repo.has_blob(sum)
        if not existing_blob and not os.path.exists(fname):
            with open(fname, "wb") as f:
                f.write(data)
        assert metadata['filename'] not in self.metadatas
        self.metadatas[metadata['filename']] = metadata
        self.resulting_blobdict[metadata['filename']] = metadata

    def add_existing(self, metadata):
        assert self.repo.has_blob(metadata['md5sum'])
        assert metadata.has_key('md5sum')
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

    def commit(self, sessioninfo = {}):
        assert self.session_path != None
        fingerprint = bloblist_fingerprint(self.resulting_blobdict.values())
        metainfo = { 'base_session': self.base_session,
                     'fingerprint': fingerprint }
        bloblist_filename = os.path.join(self.session_path, "bloblist.json")
        assert not os.path.exists(bloblist_filename)
        with open(bloblist_filename, "wb") as f:
            json.dump(self.metadatas.values(), f, indent = 4)

        session_filename = os.path.join(self.session_path, "session.json")
        assert not os.path.exists(session_filename)
        with open(session_filename, "wb") as f:
            json.dump(sessioninfo, f, indent = 4)

        meta_filename = os.path.join(self.session_path, "meta.json")
        assert not os.path.exists(meta_filename)
        with open(meta_filename, "wb") as f:
            json.dump(metainfo, f, indent = 4)

        fingerprint_marker = os.path.join(self.session_path, fingerprint + ".mark")
        with open(fingerprint_marker, "wb") as f:
            pass

        queue_dir = self.repo.get_queue_path("queued_session")
        assert not os.path.exists(queue_dir)
        
        shutil.move(self.session_path, queue_dir)
        id = self.repo.process_queue()
        return id

class SessionReader:
    def __init__(self, repo, session_path):
        assert session_path, "Session path must be given"
        self.path = session_path
        self.repo = repo
        assert os.path.exists(self.path), "No such session path:" + self.path

        path = os.path.join(self.path, "bloblist.json")
        with open(path, "rb") as f:
            self.bloblist = json.load(f)

        path = os.path.join(self.path, "session.json")
        with open(path, "rb") as f:
            self.session_info = json.load(f)

        path = os.path.join(self.path, "meta.json")
        with open(path, "rb") as f:
            self.meta_info = json.load(f)
        self.verify()        

    def verify(self):
        bloblist = self.get_all_blob_infos()
        expected_fingerprint = bloblist_fingerprint(bloblist)
        assert self.meta_info['fingerprint'] == expected_fingerprint
        contents = os.listdir(self.path)
        assert set(contents) == \
            set([expected_fingerprint+".mark",\
                     "session.json", "bloblist.json", "meta.json"]), \
                     "Missing or unexpected files in session dir: "+self.path
        for blobinfo in bloblist:
            assert repo.has_blob(blobinfo['md5sum'])
        
    def get_all_blob_infos(self):
        seen = set()
        for blobinfo in self.bloblist:
            assert blobinfo['filename'] not in seen, \
                "Internal error - duplicate file entry in a single session"
            seen.add(blobinfo['filename'])
            if blobinfo.get("action", None) == "remove":
                continue
            yield copy.copy(blobinfo)
        base_session_id = self.meta_info.get("base_session", None)
        if base_session_id:
            base_session_reader = self.repo.get_session(base_session_id)
            for info in base_session_reader.get_all_blob_infos():
                if info['filename'] not in seen:
                    # Later entries overrides earlier ones
                    yield info
