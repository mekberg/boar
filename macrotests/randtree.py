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
import hashlib


if __name__ == '__main__':
    boar_home = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, boar_home)

from common import *

allowed_chars = u" abcdefghijklmnpqrstuvwxyzåäöABCDEFGHIJKLMNPQRSTUVWXYZÅÄÖ_0123456789"

def get_random_filename(random = random):
    result = ""
    for x in range(0, random.choice([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 15, 21, 50, 200])):
        result += random.choice(allowed_chars)
    return result

class RandTree:
    def __init__(self, directory, max_path_length = VERY_LARGE_NUMBER):
        self.directory = unc_abspath(directory)
        self.dirs = [""]
        self.rnd = random.Random(0)
        self.max_path_length = max_path_length
        self.files = {} # filename -> seed integer
        self.file_data = {} # seed -> file contents (cache)

    def find_unused_filename(self, prefix = "", suffix = ""):
        for n in xrange(0, 100):
            candidate_path = self.__find_unused_filename(prefix, suffix)
            if len(candidate_path) <= self.max_path_length:
                return candidate_path
        raise Exception("Couldn't find a suitable filename within the given constraints")

    def __find_unused_filename(self, prefix, suffix):
        path = self.rnd.choice(self.dirs)
        random_base = get_random_filename(self.rnd)
        filename = os.path.join(path, prefix + random_base + suffix)
        index = 0
        while filename in self.files or filename in self.dirs:
            index += 1
            filename = os.path.join(path, prefix + random_base + str(index)+ suffix)
        return filename

    def add_dirs(self, number_of_dirs):
        for n in xrange(number_of_dirs):            
            new_dir = self.find_unused_filename(prefix = "dir_")
            assert len(new_dir) <= self.max_path_length
            self.dirs.append(new_dir)

    def add_files(self, number_of_files):
        for n in xrange(number_of_files):
            new_file = self.find_unused_filename(prefix = "file_")
            assert len(new_file) <= self.max_path_length
            self.files[new_file] = self.rnd.randint(0, 2**32)
            self.__write_file(new_file)

    def __write_file(self, fn):
            assert not os.path.isabs(fn)
            assert fn in self.files
            fullname = os.path.join(self.directory, fn)
            directory = os.path.dirname(fullname)
            if not os.path.exists(directory):
                unc_makedirs(directory)
            assert os.path.isdir(directory)
            with open(fullname, "wb") as f:
                f.write(self.get_file_data(fn))

    def modify_files(self, number_of_files):
        assert number_of_files <= len(self.files)
        winners = self.rnd.sample(self.files, number_of_files)
        for fn in winners:
            self.files[fn] += 1
            self.__write_file(fn)

    def delete_files(self, number_of_files):
        assert number_of_files <= len(self.files)
        winners = self.rnd.sample(self.files, number_of_files)
        for fn in winners:
            del self.files[fn]
            fullname = os.path.join(self.directory, fn)
            os.remove(fullname)

    def get_file_data(self, fn):
        seed = self.files[fn]
        if seed not in self.file_data:
            random.seed(seed)
            size = random.randint(0, 2**17)
            bytes = [chr(x) for x in range(0, 256)]
            self.file_data[seed] = ''.join([random.choice(bytes) for i in xrange(size)])
        return self.file_data[seed]

    def write_md5sum(self, destination, prefix = ""):
        with open(destination, "wb") as f:
            for fn in self.files:
                f.write(md5sum(self.get_file_data(fn)))
                f.write(" *")
                f.write(os.path.join(prefix, fn.encode("utf-8")))
                f.write(os.linesep)            

"""
def main():
    r = RandTree("/tmp/TESTRAND", max_path_length = 50)
    r.add_dirs(5)
    r.add_files(100)

if __name__ == "__main__":
    main()
"""
