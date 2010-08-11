from __future__ import with_statement

"""
The Repository together with SessionWriter and SessionReader are the
only classes that directly accesses the repository.
"""

import os
import re
import shutil
import sessions

#TODO: use/modify the session reader so that we don't have to use json here
import sys
if sys.version_info >= (2, 6):
    import json
else:
    import simplejson as json

from common import *


QUEUE_DIR = "queue"
BLOB_DIR = "blobs"
SESSIONS_DIR = "sessions"
TMP_DIR = "tmp"

recoverytext = """Repository format 0.1

This is a versioned repository of files. It is designed to be easy to
recover in case the original software is unavailable. This document
describes the layout of the repository, so that a programmer can
construct a simple program that recovers the data.

All files are stored verbatim in the "blobs" directory, named after
their md5 checksum, and sorted in sub directories based on the start
of their names. For instance, if a file "testimage.jpg" has the
checksum bc7b0fb8c2e096693acacbd6cb070f16, it will be stored in
blobs/bc/bc7b0fb8c2e096693acacbd6cb070f16 since the checksum starts
with the letters "bc". The filename "testimage.jpg" is discarded. The
information necessary to reconstruct a file tree is stored in a
session file.

The individual sessions are stored in the "sessions" sub
directory. Each session represents a point in time for a file
tree. The session directory contains two files, bloblist.json and
session.json. See RFC4627 for details on the json file format. For
each entry in the list of blobs, a filename and a md5 checksum is
stored. 

To restore a session, iterate over the bloblist and copy the blob with
the corresponding checksum to a file with the name specified in the
bloblist.

"""

class MisuseException(Exception):
    pass

def create_repository(repopath):
    os.mkdir(repopath)
    os.mkdir(os.path.join(repopath, QUEUE_DIR))
    os.mkdir(os.path.join(repopath, BLOB_DIR))
    os.mkdir(os.path.join(repopath, SESSIONS_DIR))
    os.mkdir(os.path.join(repopath, TMP_DIR))
    with open(os.path.join(repopath, "recovery.txt"), "w") as f:
        f.write(recoverytext)
    
class Repo:
    def __init__(self, repopath):
        # The path must be absolute to avoid problems with clients
        # that changes the cwd. For instance, fuse.
        assert(os.path.isabs(repopath)), "The repo path must be absolute"
        self.repopath = repopath
        assert os.path.exists(self.repopath), "No such directory: %s" % (self.repopath)
        self.process_queue()

    def get_repo_path(self):
        return self.repopath

    def get_queue_path(self, filename):
        return os.path.join(self.repopath, QUEUE_DIR, filename)

    def get_blob_path(self, sum):
        assert is_md5sum(sum)
        return os.path.join(self.repopath, BLOB_DIR, sum[0:2], sum)

    def has_blob(self, sum):
        path = self.get_blob_path(sum)
        return os.path.exists(path)

    def get_blob(self, sum, offset = 0, size = -1):
        """ Returns None if there is no such blob """
        path = self.get_blob_path(sum)
        with open(path, "rb") as f:
            f.seek(offset)
            data = f.read(size)
        return data
            

    def get_session_path(self, session_id):
        return os.path.join(self.repopath, SESSIONS_DIR, str(session_id))

    def get_all_sessions(self):
        session_dirs = []
        for dir in os.listdir(os.path.join(self.repopath, SESSIONS_DIR)):
            if re.match("^[0-9]+$", dir) != None:
                session_dirs.append(int(dir))
        session_dirs.sort()
        return session_dirs

    def get_session(self, id):
        assert id
        return sessions.SessionReader(self, self.get_session_path(id))

    def create_session(self, base_session = None):
        return sessions.SessionWriter(self, base_session = base_session)

    def find_next_session_id(self):
        assert os.path.exists(self.repopath)
        session_dirs = self.get_all_sessions()
        session_dirs.append(0)
        return max(session_dirs) + 1            

    def verify_all(self):
        for sid in self.get_all_sessions():
            session = sessions.SessionReader(self, sid)
            session.verify()

    def verify_blob(self, sum):
        path = self.get_blob_path(sum)
        verified_ok = (sum == md5sum_file(path))
        return verified_ok 

    def process_queue(self):        
        queued_item = self.get_queue_path("queued_session")
        if not os.path.exists(queued_item):
            return

        items = os.listdir(queued_item)

        # Check the checksums of all blobs
        for filename in items:
            if not is_md5sum(filename):
                continue
            blob_path = os.path.join(queued_item, filename)
            assert filename == md5sum_file(blob_path), "Invalid blob found in queue dir:" + blob_path
    
        # Check the existence of all required files
        # TODO: check the contents for validity
        with open(os.path.join(queued_item, "session.json"), "rb") as f:
            meta_info = json.load(f)
        contents = [x for x in os.listdir(queued_item) if not is_md5sum(x)]
        assert set(contents) == \
            set([meta_info['fingerprint']+".fingerprint",\
                     "session.json", "bloblist.json", "session.md5"]), \
                     "Missing or unexpected files in queue dir: "+str(contents)

        # Everything seems OK, move the blobs and consolidate the session
        for filename in items:
            if not is_md5sum(filename):
                continue
            blob_to_move = os.path.join(queued_item, filename)
            destination_path = self.get_blob_path(filename)
            dir = os.path.dirname(destination_path)
            if not os.path.exists(dir):
                os.mkdir(dir)
            os.rename(blob_to_move, destination_path)
            #print "Moving", os.path.join(queued_item, filename),"to", destination_path

        id = self.find_next_session_id()
        session_path = os.path.join(self.repopath, SESSIONS_DIR, str(id))
        shutil.move(queued_item, session_path)
        assert not os.path.exists(queued_item), "Queue should be empty after processing"
        #print "Done"
        return id
