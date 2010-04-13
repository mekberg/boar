from __future__ import with_statement

import hashlib
import re
import os

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
