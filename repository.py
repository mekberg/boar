import md5
import os
import tempfile
import re
import simplejson as json

QUEUE_DIR = "queue"
BLOB_DIR = "blobs"
SESSIONS_DIR = "sessions"
TMP_DIR = "tmp"

def is_md5sum(str):
    return re.match("^[0-9]+$", str) != None    

def create_repository(repopath):
    os.mkdir(repopath)
    os.mkdir(os.path.join(repopath, QUEUE_DIR))
    os.mkdir(os.path.join(repopath, BLOB_DIR))
    os.mkdir(os.path.join(repopath, SESSIONS_DIR))
    os.mkdir(os.path.join(repopath, TMP_DIR))

class Repo:
    def __init__(self, repopath):
        self.repopath = repopath

    def get_queue_path(self, filename):
        return os.path.join(self.repopath, QUEUE_DIR, filename)

    def get_blob_path(self, sum):
        assert is_md5sum(sum)
        os.path.join(session_path, sum[0:2], sum)
        return os.path.join(self.repopath, QUEUE_DIR, filename)

    def get_session_info(self, session_id):
        session_path = get_session_path(self.repopath, session_id)
    
    def get_session_path(self, session_id):
        return os.path.join(self.repopath, str(session_id))

    def find_blob(self, sum):
        """ Takes a md5sum arg as a string, and returns the path to the blob
        with that checksum, if it exists """
        for session_id in self.get_all_sessions():
            session_path = self.get_session_path(session_id)
            blob_path = os.path.join(session_path, sum)
            if os.path.exists(blob_path):
                return blob_path
        return None

    def get_all_sessions(self):
        session_dirs = []
        for dir in os.listdir(self.repopath):
            if re.match("^[0-9]+$", dir) != None:
                session_dirs.append(int(dir))
        return session_dirs

    def find_next_session_id(self):
        assert os.path.exists(self.repopath)
        session_dirs = self.get_all_sessions()
        session_dirs.append(-1)
        return max(session_dirs) + 1            

    def find_session(self, key, value):
        pass
        #for session_id in get_all_sessions(self.repopath):
            #with open("")
            #json.loads()


    def process_queue(self):        
        print "Processing queue"
        queued_item = self.get_queue_path("queued_session")
        if not os.path.exists(queued_item):
            return
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
        
        print "Done"
