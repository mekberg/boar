#!/usr/bin/env python

import os, stat, errno, sys
import fuse
from fuse import Fuse

import repository
from front import Front
from common import *

if not hasattr(fuse, '__version__'):
    raise RuntimeError, \
        "your fuse-py doesn't know of fuse.__version__, probably it's too old."

fuse.fuse_python_api = (0, 2)

hello_path = '/hello'
hello_str = 'Hello World!\n'

class MyStat(fuse.Stat):
    def __init__(self):
        self.st_mode = 0
        self.st_ino = 0
        self.st_dev = 0
        self.st_nlink = 0
        self.st_uid = 0
        self.st_gid = 0
        self.st_size = 0
        self.st_atime = 0
        self.st_mtime = 0
        self.st_ctime = 0


class HelloFS(Fuse):

    def __init__(self, front, revision, *args, **kwargs):
        Fuse.__init__(self, *args, **kwargs)
        self.front = front
        self.revision = revision
        self.bloblist = front.get_session_bloblist(revision)
        self.files = {}
        for i in self.bloblist:
            self.files[i['filename']] = i

    def getattr(self, path):
        st = MyStat()
        fn = path[1:]
        if path == '/':
            st.st_mode = stat.S_IFDIR | 0755
            st.st_nlink = 2
        elif fn in self.files.keys():
            st.st_mode = stat.S_IFREG | 0444
            st.st_nlink = 1
            st.st_size = self.files[fn]['size']
        else:
            return -errno.ENOENT
        return st

    def readdir(self, path, offset):
#        for r in  '.', '..', hello_path[1:]:
#            yield fuse.Direntry(r)
        for r in  '.', '..':
            yield fuse.Direntry(r)
        for i in self.bloblist:
            yield fuse.Direntry(i['filename'])
                

    def open(self, path, flags):
        if path != hello_path:
            return -errno.ENOENT
        accmode = os.O_RDONLY | os.O_WRONLY | os.O_RDWR
        if (flags & accmode) != os.O_RDONLY:
            return -errno.EACCES

    def read(self, path, size, offset):
        if path != hello_path:
            return -errno.ENOENT
        slen = len(hello_str)
        if offset < slen:
            if offset + size > slen:
                size = slen - offset
            buf = hello_str[offset:offset+size]
        else:
            buf = ''
        return buf

def main():
    usage="""
Userspace hello example

""" + Fuse.fusage
    repopath, sessionName = sys.argv[1:3]
    front = Front(repository.Repo(repopath))
    revision = front.find_last_revision(sessionName)
    assert revision, "No such session found: " + sessionName
    print "Connecting to revision", revision, "on session", sessionName

    server = HelloFS(front=front,
                     revision = revision,
                     version="%prog " + fuse.__version__,
                     usage=usage,
                     dash_s_do='setsingle')

    server.parse(errex=1)
    server.main()

if __name__ == '__main__':
    main()
