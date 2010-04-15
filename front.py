import repository
import simplejson as json
import base64

class Front:

    def __init__(self, repo):
        self.repo = repo

    def get_repo_path(self):
        return self.repo.get_repo_path()

    def get_session_ids(self, filter = {}):
        return self.repo.get_all_sessions()

    def get_session_info(self, id):
        session_reader = self.repo.get_session(id)
        return session_reader.session_info

    def get_session_bloblist(self, id):
        session_reader = self.repo.get_session(id)
        return session_reader.bloblist

    def create_session(self):
        self.new_session = self.repo.create_session()

    def add(self, b64data, metadata, original_sum):
        """ Must be called after a create_session()  """
        self.new_session.add(base64.b64decode(b64data), metadata, original_sum)

    def add_existing(self, metadata, sum):
        """ Must be called after a create_session(). Adds a link to a existing
        blob. Will throw an exception if there is no such blob """
        self.new_session.add_existing(metadata, sum)

    def commit(self, sessioninfo = {}):
        id = self.new_session.commit(sessioninfo)
        self.new_session = None
        return id

## Disabled until I can figure out how to make transparent 
##calls with binary data in jasonrpc
#    def get_blob(self, sum):
#        return self.repo.get_blob(sum)

    def get_blob_b64(self, sum):
        blob = self.repo.get_blob(sum)
        return base64.b64encode(blob)

    def has_blob(self, sum):
        return self.repo.has_blob(sum)

    def find_last_revision(self, session_name):
        all_sids = self.get_session_ids()
        all_sids.sort()
        all_sids.reverse()
        for sid in all_sids:
            session_info = self.get_session_info(sid)
            name = session_info.get("name", "<no name>")
            if name == session_name:
                return sid
        return None
