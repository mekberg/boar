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

def read_file(filename):
    if not os.path.exists(filename):
        return None
    with open(filename, "rb") as f:
        data = f.read()
    return data

def md5sum(data):
    m = hashlib.md5()
    m.update(data)
    return m.hexdigest()

def md5sum_file(path):
    m = hashlib.md5()
    with open(path, "rb") as f:
        data = f.read()
    m.update(data)
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
    if sys.version_info >= (2, 6):
        return os.path.relpath(path, start)
    if not path:
        raise ValueError("no path specified")
    start_list = posixpath.abspath(start).split(sep)
    path_list = posixpath.abspath(path).split(sep)
    # Work out how much of the filepath is shared by start and path.
    i = len(posixpath.commonprefix([start_list, path_list]))
    rel_list = [pardir] * (len(start_list)-i) + path_list[i:]
    if not rel_list:
        return curdir
    return join(*rel_list)


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
        return os.path.dirname(item), os.path.basename(item)

    def skip_dir(self):
        """ Prevents descent into the directory that was returned by
        next() the last time it was called. 
        """
        self.nextdir = None
