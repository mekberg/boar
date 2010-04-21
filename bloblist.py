from common import *
import os
import stat

def create_blobinfo(path, root):
    st = os.lstat(path)
    blobinfo = {}
    blobinfo["filename"] = my_relpath(path, root)
    blobinfo["md5sum"] = md5sum_file(path)
    blobinfo["ctime"] = st[stat.ST_CTIME]
    blobinfo["mtime"] = st[stat.ST_MTIME]
    blobinfo["size"] = st[stat.ST_SIZE]
    return blobinfo

class Bloblist:
    def __init__(self):
        self.bloblist = []

    def addDictlist(self,dictlist):
        self.bloblist += dictlist
    
    def addFile(self, path, root):
        blobinfo = create_blobinfo(path, root)
        self.addDict(self, blobinfo)

    def addDict(self, dict):
        # TODO: ensure there is no name collision
        self.bloblist.append(dict)

