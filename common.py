from __future__ import with_statement

import md5
import re
import os

def is_md5sum(str):
    return re.match("^[a-f0-9]{32}$", str) != None    

assert is_md5sum("7df642b2ff939fa4ba27a3eb4009ca67")

def read_file(filename):
    if not os.path.exists(filename):
        return None
    with open(filename, "r") as f:
        data = f.read()
    return data

def md5sum(data):
    m = md5.new()
    m.update(data)
    return m.hexdigest()

