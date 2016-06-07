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

from optparse import OptionParser
from common import get_tree, tounicode, md5sum_file

def main():
    args = sys.argv[1:]
    if len(args) == 0:
        args = ["--help"]
    parser = OptionParser(usage="usage: treecheck.py [-f <md5file>] <path>")
    parser.add_option("-f", "--filename", action="store", dest = "filename", type="string",
                      help="A file describing the expected directory contents (md5sum.exe file format)")
    (options, args) = parser.parse_args(args)
    path = tounicode(args[0])
    if not os.path.isabs(path):
        path = tounicode(os.getcwd()) + u"/" + path
    assert os.path.exists(path), "Path does not exist: " + path

    if options.filename == "-":
        fo = sys.stdin
    else:
        fo = open(tounicode(options.filename))
    expected = {}
    for line in fo:
        expected[line[34:].strip()] = line[0:32]

    tree = get_tree(path)

    extra_files = []
    diff_files = []
    missing_files = []

    for fn in tree:
        md5 = md5sum_file(fn)
        if fn not in expected:
            extra_files.append(fn)
            print "?", fn
        else:
            if expected[fn] != md5:
                diff_files.append(fn)
                print "M", fn
    for fn in expected.keys():
        if fn not in tree:
            missing_files.append(fn)
            print "D", fn

    if extra_files or diff_files or missing_files:
        print >>sys.stderr, "*** Content does not match"
        sys.exit(1)

main()
