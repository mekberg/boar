import md5
import os
import tempfile
import re
import simplejson as json

class Repo:

    def __init__(self, repopath):
        self.repopath = repopath

    def get_session_info(self, session_id):
        session_path = get_session_path(self.repopath, session_id)
    

    def get_session_path(self, session_id):
        return os.path.join(self.repopath, str(session_id))

#    def get_blob_path(repopath, sum):
#        os.path.join(session_path, sum[0:2], sum)

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

