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

base_id: The revision id of the revision that this revision is based
        on. May be null in case of a non-incremental revision.


"""

class AddException(Exception):
    pass

def bloblist_to_dict(bloblist):
    d = {}
    for b in bloblist:
        d[b['filename']] = b
    return d

class SessionWriter:
    def __init__(self, repo, base_id = None):
        self.repo = repo
        self.base_id = base_id
        self.session_path = None
        self.metadatas = {}
        assert os.path.exists(self.repo.repopath)
        self.session_path = tempfile.mkdtemp( \
            prefix = "tmp_", 
            dir = os.path.join(self.repo.repopath, repository.TMP_DIR)) 
        
        self.base_session_info = {}
        self.base_bloblist_dict = {}
        if self.base_id != None:
            self.base_session_info = self.repo.get_session(self.base_id).session_info
            self.base_bloblist_dict = bloblist_to_dict(self.repo.get_session(self.base_id).bloblist)

    def add(self, data, metadata, original_sum):
        assert data != None
        assert metadata != None
        assert is_md5sum(original_sum)
        assert self.session_path != None
        sum = md5sum(data)
        if original_sum and (sum != original_sum):
            raise AddException("Calculated checksum did not match client provided checksum")
        metadata["md5sum"] = sum
        fname = os.path.join(self.session_path, sum)
        existing_blob = self.repo.has_blob(sum)
        if not existing_blob and not os.path.exists(fname):
            with open(fname, "wb") as f:
                f.write(data)
        assert metadata['filename'] not in self.metadatas
        self.metadatas[metadata['filename']] = metadata

    def add_existing(self, metadata, sum):
        assert self.repo.has_blob(sum)
        metadata["md5sum"] = sum
        assert metadata['filename'] not in self.metadatas
        self.metadatas[metadata['filename']] = metadata

    def remove(self, filename):
        assert filename in self.metadatas
        del self.metadatas['filename']

    def commit(self, sessioninfo = {}):
        assert self.session_path != None
        sessioninfo['base_id'] = self.base_id
        bloblist_filename = os.path.join(self.session_path, "bloblist.json")
        assert not os.path.exists(bloblist_filename)
        with open(bloblist_filename, "wb") as f:
            json.dump(self.metadatas.values(), f, indent = 4)

        session_filename = os.path.join(self.session_path, "session.json")
        assert not os.path.exists(session_filename)
        with open(session_filename, "wb") as f:
            json.dump(sessioninfo, f, indent = 4)

        queue_dir = self.repo.get_queue_path("queued_session")
        assert not os.path.exists(queue_dir)

        print "Committing to", queue_dir, "from", self.session_path, "..."
        shutil.move(self.session_path, queue_dir)
        print "Done committing."
        print "Consolidating changes..."
        id = self.repo.process_queue()
        print "Consolidating changes complete"
        return id

checked_blobs = {}

class SessionReader:
    def __init__(self, repo, session_id):
        self.path = repo.get_session_path(session_id)
        self.session_id = session_id
        self.repo = repo
        assert os.path.exists(self.path)

        path = os.path.join(self.path, "bloblist.json")
        with open(path, "rb") as f:
            self.bloblist = json.load(f)

        path = os.path.join(self.path, "session.json")
        with open(path, "rb") as f:
            self.session_info = json.load(f)

    def verify(self):
        for blobinfo in self.bloblist:
            sum = blobinfo['md5sum']
            if checked_blobs.has_key(sum):
                is_ok = checked_blobs[sum]
            else:
                is_ok = self.repo.verify_blob(blobinfo['md5sum'])
                checked_blobs[sum] = is_ok
            print blobinfo['filename'], is_ok
            
    def get_all_files(self):
        for blobinfo in self.bloblist:
            info = copy.copy(blobinfo)
            with open(self.repo.get_blob_path(info['md5sum']), "r") as f:
                info['data'] = f.read()
            assert md5sum(info['data']) == info['md5sum']
            yield info
    
if __name__ == "__main__":
    main()

