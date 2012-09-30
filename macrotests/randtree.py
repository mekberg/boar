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
import array
from mkrandfile import mkrandfile_fast
allowed_chars = u" abcdefghijklmnpqrstuvwxyzåäöABCDEFGHIJKLMNPQRSTUVWXYZÅÄÖ_0123456789"

def get_random_filename(random = random):
    result = ""
    for x in range(0, random.choice([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 15, 21, 50, 200])):
        result += random.choice(allowed_chars)
    return result

def find_unused_filename(path, prefix = "", suffix = "", random = random):
    random_base = get_random_filename(random = random)
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

class RandTree:
    def __init__(self):
        self.dirs = [""]
        self.rnd = random.Random(0)
        self.files = {} # filename -> seed integer

    def find_unused_filename(self, path, prefix = "", suffix = ""):
        random_base = get_random_filename(self.rnd)
        filename = os.path.join(path, prefix + random_base + suffix)
        index = 0
        while filename in self.files or filename in self.dirs:
            index += 1
            filename = os.path.join(path, prefix + random_base + str(index)+ suffix)
        return filename

    def add_dirs(self, number_of_dirs):
        for n in xrange(number_of_dirs):
            parent = self.rnd.choice(self.dirs)
            new_dir = self.find_unused_filename(parent, prefix = "dir_")
            self.dirs.append(new_dir)

    def add_files(self, number_of_files):
        for n in xrange(number_of_files):
            parent = self.rnd.choice(self.dirs)
            new_file = self.find_unused_filename(parent, prefix = "file_")
            self.files[new_file] = self.rnd.randint(0, 2**32)

    def modify_files(self, number_of_files):
        assert number_of_files <= len(self.files)
        winners = self.rnd.sample(self.files, number_of_files)
        for fn in winners:
            self.files[fn] += 1

    def delete_files(self, number_of_files):
        assert number_of_files <= len(self.files)
        winners = self.rnd.sample(self.files, number_of_files)
        for fn in winners:
            del self.files[fn]

    def get_file_data(self, fn):
        random.seed(self.files[fn])
        data_array = array.array("B") # unsigned chars
        size = random.randint(0, 2**16)
        for x in xrange(0, size):
            data_array.append(random.randrange(256))
        data = data_array.tostring()
        assert len(data) == size
        return data

def main():
    r = RandTree()
    
def main_old():
    #dirname, count, size = sys.argv[1:]
    dirname, dircount, filecount, total_size = sys.argv[1:]
    os.mkdir(dirname)
    random.seed((dircount, filecount)) # Make deterministic
    add_random_tree(dirname, int(dircount), int(filecount), int(total_size))

if __name__ == "__main__":
    main()
