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
        sessions = self.repo.get_all_sessions()
        print "Get all session ids:", sessions
        return sessions

    def create_session(self):
        self.new_session = sessions.SessionWriter(self.repo)

    def add(self, data, metadata = {}, original_sum = None):
        """ Must be called after a create_session()  """
        self.new_session.add(data, metadata, original_sum)

    def commit(self, sessioninfo = {}):
        self.new_session.commit(sessioninfo)
        self.new_session = None

    def get_file(self, sum):
        return self.repo.get_blob(sum)

