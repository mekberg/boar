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

if __name__ == '__main__':
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

    assert not os.path.exists(filename)

    md5 = hashlib.md5()
    f = open(filename, "wb")
    for n in xrange(0, filesize_kbytes*128):
        byte_val = random.randint(0, 2**32-1)
        buf = struct.pack("Q", byte_val)
        f.write(buf)
        md5.update(buf)
    f.close()
    assert md5sum_file(filename) == md5.hexdigest()
    assert os.path.getsize(filename) == filesize_kbytes * 1024
    print "%s  %s" % (md5.hexdigest(), filename)

main()
