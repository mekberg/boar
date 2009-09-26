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

    def get_all_session_ids(self):
        sessions = self.repo.get_all_sessions()
        print "Get all session ids:", sessions
        return sessions

    def create_session(self):
        self.new_session = sessions.SessionWriter(self.repo)

    def add(self, data, metadata = {}, original_sum = None):
        self.new_session.add(data, metadata, original_sum)

    def commit(self, sessioninfo = {}):
        self.new_session.commit(sessioninfo)

    def init_co(self, session_id):
        print "Init co for session", session_id
        session = self.repo.get_session(session_id)
        self.files_generator = session.get_all_files()

    def get_next_file(self):
        try:
            info = self.files_generator.next()
        except StopIteration:
            print "No more files"
            return None
        print info['filename'], info['size']

        info['data_b64'] = base64.b64encode(info['data'])
        del info['data']
        return info

