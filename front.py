import repository
import simplejson as json
import base64

class Front:

    def __init__(self, repo):
        self.repo = repo
        

    def open(self):
        pass

    def close(self):
        pass

    def hello(self):
        print "Somebody said hello"
        return "Hello!"

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

    def add(self, data, metadata = {}, original_sum = None):
        """ Must be called after a create_session()  """
        self.new_session.add(data, metadata, original_sum)

    def commit(self, sessioninfo = {}):
        id = self.new_session.commit(sessioninfo)
        self.new_session = None
        return id

    def get_blob(self, sum):
        return self.repo.get_blob(sum)

