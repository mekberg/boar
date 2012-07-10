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
import re

from optparse import OptionParser

def read_file(filename):
    if filename == "-":
        lines = sys.stdin.readlines()
    else:
        with open(filename, "rb") as f:
            lines = f.readlines()
    return map(lambda s: s.rstrip("\n\r"), lines)

def match_line(pattern, text, magic_string):
    if pattern.startswith(magic_string):
        repattern = pattern[len(magic_string):]
        return (re.match("^" + repattern + "$", text) != None)
    else:
        return (pattern == text)
    

def txtmatch(pattern_lines, text_lines, magic_string = None):
    def print_error(pattern_lines, text_lines):
        for line in pattern_lines:
            print "expected:", line
        for line in text_lines:
            print "actual  :", line

    if len(pattern_lines) != len(text_lines):
        print "*** Length mismatch"
        print_error(pattern_lines, text_lines)
        return False
    for i in range(0, len(pattern_lines)):
        text = text_lines[i]
        pattern = pattern_lines[i]
        if not match_line(pattern, text, magic_string):
            print "Mismatch at line", i, "(magic = '%s')" % magic_string
            print_error(pattern_lines, text_lines)
            return False
    return True

def main():
    args = sys.argv[1:]
    if len(args) == 0:
        args = ["--help"]
    parser = OptionParser(usage="usage: txtmatch.py [-c <magic string>] <pattern file> <text file>")
    parser.add_option("-c", "--magic", action="store", dest = "magic", type="string", default="!",
                      help="The initial string that indicates that this line is a regular expression. Default is '!'")
    (options, args) = parser.parse_args(args)
    if len(args) == 1:
        args.append("-")
    pattern_file, text_file = args
    assert not (pattern_file == "-" and text_file == "-"), "Only one input can be stdin"
    pattern_lines = read_file(pattern_file)
    text_lines = read_file(text_file)

    if not txtmatch(pattern_lines, text_lines, magic_string = options.magic):
        print >>sys.stderr, "*** Text mismatch"
        sys.exit(1)
    sys.exit(0)

main()
