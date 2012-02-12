#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2011 Mats Ekberg
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
import sys
import os
import time
import random
from mkrandfile import mkrandfile
allowed_chars = u" abcdefghijklmnpqrstuvwxyzåäöABCDEFGHIJKLMNPQRSTUVWXYZÅÄÖ_0123456789"

def get_random_filename(size = 5):
    result = ""
    for x in range(0, size):
        result += random.choice(allowed_chars)
    return result

def find_unused_filename(path, prefix = ""):
    random_base = get_random_filename()
    filename = path + "/" + prefix + random_base + ".bin"
    index = 0
    while os.path.exists(filename):
        index += 1
        filename = path + "/" + random_base + str(index) + ".bin"
    return filename

def add_randomized_file(path):
    filename = find_unused_filename(path)
    write_random_contents(filename, 1)

def write_random_contents(filename, count):
    assert not os.path.exists(filename)
    mkrandfile(filename, count)

def add_random_files(path, count, filesize_kb):
    for x in range(0, count):
        add_randomized_file(path)    

def add_random_tree(path, total_dirs, total_files):
    existing_dirs = [path]
    for n in xrange(total_dirs):
        print "Creating dirs", n, "\r",
        sys.stdout.flush()
        parent = random.choice(existing_dirs)
        new_dir = find_unused_filename(parent, prefix = "dir_")
        os.mkdir(new_dir)
        existing_dirs.append(new_dir)
    for n in xrange(total_files):
        print "Creating files", n, "\r",
        sys.stdout.flush()
        parent = random.choice(existing_dirs)
        add_randomized_file(parent)

def main():
    #dirname, count, size = sys.argv[1:]
    #add_random_files(dirname, int(count), int(size))
    dirname, dircount, filecount = sys.argv[1:]
    os.mkdir(dirname)
    random.seed((dircount, filecount)) # Make deterministic
    add_random_tree(dirname, int(dircount), int(filecount))

if __name__ == "__main__":
    main()
