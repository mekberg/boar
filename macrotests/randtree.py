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
from mkrandfile import mkrandfile_fast
allowed_chars = u" abcdefghijklmnpqrstuvwxyzåäöABCDEFGHIJKLMNPQRSTUVWXYZÅÄÖ_0123456789"

def get_random_filename():
    result = ""
    for x in range(0, random.choice([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 15, 21, 50, 200])):
        result += random.choice(allowed_chars)
    return result

def find_unused_filename(path, prefix = "", suffix = ""):
    random_base = get_random_filename()
    filename = path + "/" + prefix + random_base + suffix
    index = 0
    while os.path.exists(filename):
        index += 1
        filename = path + "/" + prefix + random_base + str(index) + suffix
    return filename

def add_randomized_file(path, file_size = 0):
    filename = find_unused_filename(path)
    write_random_contents(filename, file_size)

def write_random_contents(filename, file_size_bytes):
    assert not os.path.exists(filename)
    mkrandfile_fast(filename, file_size_bytes/1024)

def add_random_tree(path, total_dirs, total_files, total_size):
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
        add_randomized_file(parent, total_size / total_files)

def main():
    #dirname, count, size = sys.argv[1:]
    dirname, dircount, filecount, total_size = sys.argv[1:]
    os.mkdir(dirname)
    random.seed((dircount, filecount)) # Make deterministic
    add_random_tree(dirname, int(dircount), int(filecount), int(total_size))

if __name__ == "__main__":
    main()
