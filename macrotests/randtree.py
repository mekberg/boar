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

allowed_chars = u" abcdefghijklmnpqrstuvwxyzåäöABCDEFGHIJKLMNPQRSTUVWXYZÅÄÖ_0123456789"

def get_random_filename(size = 5):
    result = ""
    for x in range(0, size):
        result += random.choice(allowed_chars)
    return result

def add_randomized_file(path):
    random_base = get_random_filename()
    filename = path + "/" + random_base + ".bin"
    index = 0
    while os.path.exists(filename):
        index += 1
        filename = path + "/" + random_base + str(index) + ".bin"
    write_random_contents(filename, 1)

def write_random_contents(filename, count, blocksize = 1024):
    assert not os.path.exists(filename)
    with open(filename, "w") as f:
        with open("/dev/urandom", "r") as rand:
            for x in range(0, count):
                f.write(rand.read(blocksize))

def add_random_files(path, count, filesize_kb):
    for x in range(0, count):
        add_randomized_file(path)    

def main():
    random.seed(0) # Make deterministic
    dirname, count, size = sys.argv[1:]
    add_random_files(dirname, int(count), int(size))

if __name__ == "__main__":
    main()
