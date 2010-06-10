#!/usr/bin/env python

import os, stat, errno, sys
import fuse
from fuse import Fuse

from blobrepo import repository
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
        bloblist = front.get_session_bloblist(revision)
        self.files = {}
        for i in bloblist:
            i['type'] = "file"
            i['dir'] = "/" + os.path.dirname(i['filename'])
            assert i['filename'] not in self.files, "Dupes in bloblist - repository corruption?"
            self.files[i['filename']] = i
            dirname = os.path.dirname(i['filename'])
            if dirname and dirname not in self.files: # Don't add an empty top dir name
                self.files[dirname] = { 'filename': dirname, 'type': 'directory', 'size': 0, 'dir': "/" + os.path.dirname(dirname) }
        

    def getattr(self, path):
        st = MyStat()
        st.st_uid = os.geteuid()
        st.st_gid = os.getegid()
        fn = path[1:]
        if path == '/':
            st.st_mode = stat.S_IFDIR | 0755
            st.st_nlink = 2
        elif fn in self.files.keys():
            info = self.files[fn]
            if info['type'] == 'file':
                st.st_mode = stat.S_IFREG | 0444
                st.st_nlink = 1
                st.st_size = self.files[fn]['size']
                st.st_mtime = self.files[fn]['mtime']
                st.st_ctime = self.files[fn]['ctime']
            elif info['type'] == 'directory':
                st.st_mode = stat.S_IFDIR | 0755
                st.st_nlink = 2
        else:
            return -errno.ENOENT
        return st

    def readdir(self, path, offset):
        #        for r in  '.', '..', hello_path[1:]:
        print "Readdir(", path, ",", offset, ")"
        #            yield fuse.Direntry(r)
        for r in  '.', '..':
            yield fuse.Direntry(r)
        for i in self.files.values():
            fn = i['filename']
            if i['dir'] == path:
                yield fuse.Direntry(os.path.basename(str(fn)))
                

    def open(self, path, flags):
        fn = path[1:]
        if fn not in self.files:
            return -errno.ENOENT
        accmode = os.O_RDONLY | os.O_WRONLY | os.O_RDWR
        if (flags & accmode) != os.O_RDONLY:
            return -errno.EACCES

    def read(self, path, size, offset):
        fn = path[1:]
        if fn not in self.files:
            return -errno.ENOENT
        try:
            repo = self.front.repo        
            fileinfo=self.files[fn]
            assert repo.has_blob(fileinfo['md5sum']), "Blob does not exist in the repository. Corrupt repo?"
            realpath = repo.get_blob_path(fileinfo['md5sum'])
            with open(realpath, "rb") as blob:
                blob.seek(offset)
                buf = blob.read(size)
        except Exception as e:
            return "error! " + repr(e)
        return buf

def main():
    usage="""
Userspace hello example

""" + Fuse.fusage
    repopath, sessionName = sys.argv[1:3]
    repopath = os.path.abspath(repopath)
    front = Front(repository.Repo(repopath))
    revision = front.find_last_revision(sessionName)
    assert revision != None, "No such session found: " + sessionName
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
