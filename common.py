from __future__ import with_statement

import md5
import re
import os

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
    m = md5.new()
    m.update(data)
    return m.hexdigest()

def md5sum_file(path):
    m = md5.new()
    with open(path, "rb") as f:
        data = f.read()
    m.update(data)
    return m.hexdigest()
