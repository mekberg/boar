from __future__ import with_statement

import hashlib
import re
import os
import sys

""" This file contains code that is generally useful, without being
specific for any project """

def is_md5sum(str):
    try:
        return re.match("^[a-f0-9]{32}$", str) != None    
    except TypeError:
        return False

assert is_md5sum("7df642b2ff939fa4ba27a3eb4009ca67")

def md5sum(data):
    m = hashlib.md5()
    m.update(data)
    return m.hexdigest()

def md5sum_file(path):
    m = hashlib.md5()
    with open(path, "rb") as f:
        while True:
            data = f.read(2 ** 20)
            m.update(data)
            if data == "":
                break
    return m.hexdigest()

def convert_win_path_to_unix(path):
    """ Converts "C:\\dir\\file.txt" to "/dir/file.txt". 
        Has no effect on unix style paths. """
    nodrive = os.path.splitdrive(path)[1]
    return nodrive.replace("\\", "/")

def get_relative_path(p):
    """ Normalizes the path to unix format and then removes drive letters
    and/or slashes from the given path """
    p = convert_win_path_to_unix(p)
    while True:
        if p.startswith("/"):
            p = p[1:]
        elif p.startswith("./"):
            p = p[2:]
        else:
            return p

def strip_path_offset(offset, p):
    """ Removes the initial part of pathname p that is identical to
    the given offset. Example: strip_path_offset("myfiles",
    "myfiles/dir1/file.txt") => "dir1/file.txt" """
    # TODO: For our purposes, this function really is a dumber version
    # of my_relpath(). One should replace the other.
    if offset == "":
        return p
    assert p.startswith(offset)
    assert p[len(offset)] == "/"
    return p[len(offset)+1:]

def remove_first_dirname(p):
    rel_path = get_relative_path(p)
    firstslash = rel_path.find("/")
    if firstslash == -1:
        return None
    rest = rel_path[firstslash+1:]
    # Let's just trim any double slashes
    rest = get_relative_path(rest)
    return rest

assert remove_first_dirname("tjosan/hejsan") == "hejsan"


import os.path as posixpath
from os.path import curdir, sep, pardir, join
# Python 2.5 compatible relpath(), Based on James Gardner's relpath
# function.
# http://www.saltycrane.com/blog/2010/03/ospathrelpath-source-code-python-25/
def my_relpath(path, start=curdir):
    """Return a relative version of a path"""
    assert os.path.isabs(path)
    if sys.version_info >= (2, 6):
        result = os.path.relpath(path, start)
        #print "relpath(path=%s, start=%s) => %s" % (path, start, result)
        return result
    if not path:
        raise ValueError("no path specified")
    start_list = posixpath.abspath(start).split(sep)
    path_list = posixpath.abspath(path).split(sep)
    # Work out how much of the filepath is shared by start and path.
    i = len(posixpath.commonprefix([start_list, path_list]))
    rel_list = [pardir] * (len(start_list)-i) + path_list[i:]
    if not rel_list:
        result = curdir
    else:
        result = join(*rel_list)
    #print "my_relpath(path=%s, start=%s) => %s" % (path, start, result)
    return result

def open_raw(filename):
    """Try to read the file in such a way that the system file cache
    is not used."""
    # TODO: implement
    return open(filename, "rb")
    # This does not work for some reason:
    # try:
    #     fd = os.open(filename, os.O_DIRECT | os.O_RDONLY, 10000000)
    #     print "Successfully using O_DIRECT"
    #     return os.fdopen(fd, "rb", 10000000)
    # except Exception, e:
    #     print "Failed using O_DIRECT", e
    #     return open(filename, "rb")

class TreeWalker:
    def __init__(self, path):
        assert os.path.exists(path)
        self.queue = [path]
        self.nextdir = None

    def __iter__(self):
        return self

    def next(self):
        """ Returns the next entry as a tuple, (dirname, entryname) """
        if self.nextdir:
            for name in os.listdir(self.nextdir):
                self.queue.append(os.path.join(self.nextdir, name))
            self.nextdir = None
        if not self.queue:
            raise StopIteration()
        item = self.queue.pop(0)
        if os.path.isdir(item):
            self.nextdir = item
        result = os.path.dirname(item), os.path.basename(item)
        return result

    def skip_dir(self):
        """ Prevents descent into the directory that was returned by
        next() the last time it was called. 
        """
        self.nextdir = None

