""" The Front class is a facade for the Repository, SessionWriter and
SessionReader classes. It provides some convenience methods, but its
primary purpose is to provide an interface that is easy to use over
RPC. All arguments and return values are primitive values that can be
serialized easily.
"""


from blobrepo import repository
import sys

if sys.version_info >= (2, 6):
    import json
else:
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
        bloblist = list(session_reader.get_all_blob_infos())
        seen = set()
        for b in bloblist:
            assert b['filename'] not in seen, "Duplicate file found in bloblist - internal error"
            seen.add(b['filename'])
        return bloblist

    def create_session(self, base_session = None):
        self.new_session = self.repo.create_session(base_session)

    def add_blob_data(self, blob_md5, b64data):
        """ Must be called after a create_session()  """
        self.new_session.add_blob_data(blob_md5, base64.b64decode(b64data))

    def add(self, metadata):
        """ Must be called after a create_session(). Adds a link to a existing
        blob. Will throw an exception if there is no such blob """
        assert metadata.has_key("md5sum")
        self.new_session.add(metadata)

    def remove(self, filename):
        """ Remove the given file in the workdir from the current
        session. Requires that the current session has a base
        session""" 
        self.new_session.remove(filename)

    def commit(self, sessioninfo = {}):
        id = self.new_session.commit(sessioninfo)
        self.new_session = None
        return id

## Disabled until I can figure out how to make transparent 
##calls with binary data in jasonrpc
#    def get_blob(self, sum):
#        return self.repo.get_blob(sum)

    def get_blob_size(self, sum):
        return self.repo.get_blob_size(sum)

    def get_blob_b64(self, sum, offset = 0, size = -1):
        blobpart = self.repo.get_blob(sum, offset, size)
        return base64.b64encode(blobpart)

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
