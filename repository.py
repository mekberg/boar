from __future__ import with_statement

import md5
import os
import re
import shutil
import simplejson as json
import sessions

QUEUE_DIR = "queue"
BLOB_DIR = "blobs"
SESSIONS_DIR = "sessions"
TMP_DIR = "tmp"

def is_md5sum(str):
    return re.match("^[a-f0-9]{32}$", str) != None    

assert is_md5sum("7df642b2ff939fa4ba27a3eb4009ca67")

def create_repository(repopath):
    os.mkdir(repopath)
    os.mkdir(os.path.join(repopath, QUEUE_DIR))
    os.mkdir(os.path.join(repopath, BLOB_DIR))
    os.mkdir(os.path.join(repopath, SESSIONS_DIR))
    os.mkdir(os.path.join(repopath, TMP_DIR))

class Repo:
    def __init__(self, repopath):
        self.repopath = repopath
        assert os.path.exists(self.repopath)
        self.process_queue()

    def get_queue_path(self, filename):
        return os.path.join(self.repopath, QUEUE_DIR, filename)

    def get_blob_path(self, sum):
        assert is_md5sum(sum)
        return os.path.join(self.repopath, BLOB_DIR, sum[0:2], sum)

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
        return sessions.SessionReader(self, id)

    def create_session(self):
        return sessions.SessionWriter(self)

    def find_next_session_id(self):
        assert os.path.exists(self.repopath)
        session_dirs = self.get_all_sessions()
        session_dirs.append(-1)
        return max(session_dirs) + 1            

    def verify_all(self):
        for sid in self.get_all_sessions():
            session = sessions.SessionReader(self, sid)
            session.verify()

    def verify_blob(self, sum):
        path = self.get_blob_path(sum)
        with open(path, "r") as f:
            verified_ok = (sum == sessions.md5sum(f.read()))
        return verified_ok 

    def process_queue(self):        
        queued_item = self.get_queue_path("queued_session")
        if not os.path.exists(queued_item):
            return
        print "Processing queue"
        items = os.listdir(queued_item)
        for filename in items:
            if not is_md5sum(filename):
                continue
            destination_path = self.get_blob_path(filename)
            dir = os.path.dirname(destination_path)
            if not os.path.exists(dir):
                os.mkdir(dir)
            os.rename(os.path.join(queued_item, filename), destination_path)
            print "Moving", os.path.join(queued_item, filename),"to", destination_path
        assert set(os.listdir(queued_item)) == set(["session.json", "bloblist.json"]), \
            "Unexpected or missing files in queue dir"
        id = self.find_next_session_id()
        session_path = os.path.join(self.repopath, SESSIONS_DIR, str(id))
        shutil.move(queued_item, session_path)
        assert not os.path.exists(queued_item), "Queue should be empty after processing"
        print "Done"
        return id
