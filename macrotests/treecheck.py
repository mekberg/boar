#!/usr/bin/env python3
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
from common import tounicode
from file_scanner import FileScanner

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

    scanner = FileScanner([path], relative_to=path)
    scan_results = scanner.scan()
    tree = list(scan_results.keys())

    extra_files = []
    diff_files = []
    missing_files = []

    for fn, info in scan_results.items():
        md5 = info["md5"]
        if fn not in expected:
            extra_files.append(fn)
            print("?", fn)
        else:
            if expected[fn] != md5:
                diff_files.append(fn)
                print("M", fn)
    for fn in list(expected.keys()):
        if fn not in tree:
            missing_files.append(fn)
            print("D", fn)

    if extra_files or diff_files or missing_files:
        print("*** Content does not match", file=sys.stderr)
        sys.exit(1)

main()
