#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2012 Mats Ekberg
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

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common import tounicode, md5sum_file
import hashlib
import random
import struct

def main():
    args = sys.argv[1:]
    if len(args) != 3:
        print "mkrandfile.py <seed integer> <filesize in kb> <filename>"
        sys.exit(1)

    seed = int(args.pop(0))
    filesize_kbytes = int(args.pop(0))
    filename = tounicode(args.pop(0))
    random.seed(seed)
    md5 = mkrandfile(filename, filesize_kbytes)
    print md5 + "  " + filename

def mkrandfile_deterministic(path, filesize_kbytes):
    assert not os.path.exists(path)
    md5 = hashlib.md5()
    f = open(path, "wb")
    for n in xrange(0, filesize_kbytes*128):
        byte_val = random.randint(0, 2**32-1)
        buf = struct.pack("Q", byte_val)
        f.write(buf)
        md5.update(buf)
    f.close()
    assert md5sum_file(path) == md5.hexdigest()
    assert os.path.getsize(path) == filesize_kbytes * 1024
    return md5.hexdigest()

def mkrandfile_fast(path, filesize_kbytes):
    assert not os.path.exists(path)
    md5 = hashlib.md5()
    fw = open(path, "wb")
    fr = open("/dev/urandom", "rb")
    remaining_kbytes = filesize_kbytes
    while remaining_kbytes:
        buf = fr.read(1024)
        fw.write(buf)
        md5.update(buf)
        remaining_kbytes -= 1
    fw.close()
    fr.close()
    #assert md5sum_file(path) == md5.hexdigest()
    #assert os.path.getsize(path) == filesize_kbytes * 1024
    return md5.hexdigest()

if __name__ == "__main__":
    main()
