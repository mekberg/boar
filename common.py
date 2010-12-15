# -*- coding: utf-8 -*-

# Copyright 2010 Mats Ekberg
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import with_statement

import hashlib
import re
import os
import sys
import platform

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
    assert isinstance(path, unicode)
    nodrive = os.path.splitdrive(path)[1]
    result = nodrive.replace("\\", "/")
    #print "convert_win_path_to_unix: " + path + " => " + result
    return result

def is_windows_path(path):
    return "\\" in path

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

# This method avoids an infinite loop when add_path_offset() and
# strip_path_offset() verfies the results of each other.
def __add_path_offset(offset, p):
    return offset + "/" + p

def add_path_offset(offset, p):
    result = __add_path_offset(offset, p)
    assert strip_path_offset(offset, result) == p
    return result

def strip_path_offset(offset, p):
    """ Removes the initial part of pathname p that is identical to
    the given offset. Example: strip_path_offset("myfiles",
    "myfiles/dir1/file.txt") => "dir1/file.txt" """
    # TODO: For our purposes, this function really is a dumber version
    # of my_relpath(). One should replace the other.
    if offset == "":
        return p
    assert not offset.endswith("/"), "Offset must be given without ending slash. Was: "+offset
    assert p.startswith(offset), "'%s' does not begin with offset '%s'" % (p, offset)
    assert p[len(offset)] == "/", "Offset was: "+offset+" Path was: "+p
    result = p[len(offset)+1:]
    assert __add_path_offset(offset, result) == p
    return result

def is_child_path(parent, child):
    if parent == "":
        return True
    result = child.startswith(parent + "/")
    #print "is_child_path('%s', '%s') => %s" % (parent, child, result)
    return result
    
def remove_first_dirname(p):
    assert isinstance(p, unicode)
    rel_path = get_relative_path(p)
    firstslash = rel_path.find("/")
    if firstslash == -1:
        return None
    rest = rel_path[firstslash+1:]
    # Let's just trim any double slashes
    rest = get_relative_path(rest)
    return rest

assert remove_first_dirname(u"tjosan/hejsan") == "hejsan"


import os.path as posixpath
from os.path import curdir, sep, pardir, join
# Python 2.5 compatible relpath(), Based on James Gardner's relpath
# function.
# http://www.saltycrane.com/blog/2010/03/ospathrelpath-source-code-python-25/
def my_relpath(path, start=curdir):
    """Return a relative version of a path"""
    assert os.path.isabs(path)
    if not path:
        raise ValueError("no path specified")
    assert isinstance(path, unicode)
    assert isinstance(start, unicode)
    absstart = posixpath.abspath(start)
    abspath = posixpath.abspath(path)
    if absstart[-1] != os.path.sep:
        absstart += os.path.sep
    assert abspath.startswith(absstart), abspath + " " + absstart    
    return abspath[len(absstart):]

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

def get_tree(root, skip = [], absolute_paths = False):
    """ Returns a simple list of all the files and directories in the
        workdir (except meta directories). """
    assert isinstance(root, unicode) # type affects os.path.walk callback args
    def visitor(out_list, dirname, names):
        for file_to_skip in skip:
            if file_to_skip in names:
                names.remove(file_to_skip)
        for name in names:
            try:
                fullpath = os.path.join(dirname, name)
            except:
                print "Failed on file:", dirname, name
                raise
            if not os.path.isdir(fullpath):
                out_list.append(fullpath)
    all_files = []
    os.path.walk(root, visitor, all_files)
    remove_rootpath = lambda fn: convert_win_path_to_unix(my_relpath(fn, root))
    if not absolute_paths:
        all_files = map(remove_rootpath, all_files)
    for f in all_files:
        assert not is_windows_path(f), "Was:" + f
        assert not ".." in f.split("/"), "Was:" + f
        assert not "\\" in f, "Was:" + f
    return all_files


class UNUSED_TreeWalker:
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

