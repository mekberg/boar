#!/usr/bin/python
import md5
import os

def md5sum(data):
    m = md5.new()
    m.update(data)
    return m.hexdigest()




class RepoWriter:

    def __init__(self):
        self.repopath = "REPO"
        self.Session = None

    def new_session(self, session_name):
        assert self.Session == None
        assert os.path.exists(self.repopath)

    def add(self, data, file_path):
        # assert self.Session != None
        fname = os.path.join(self.repopath, "blobs", md5sum(data))
        assert not os.path.exists(fname)
        f = open(fname, "w")
        f.write(data)
        f.close()

    def close_session(self):
        assert self.Session != None
        assert False, "Not implemented"

class RepoReader:

    def __init__(self):
        self.Session = None

    def open(self, session_name):
        assert self.Session == None

    def get(self, file_path):
        assert self.Session != None
        assert False, "Not implemented"

    def get_session_names(self):
        assert False, "Not implemented"



def main():
    s = RepoWriter()
    s.new_session("new_session")

    file_to_add = "promenader.txt"
    data = open(file_to_add, "r").read()
    s.add(data, file_to_add)
    
    
if __name__ == "__main__":
    main()

