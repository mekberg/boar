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

from common import *
import sys

class BlockChecksum:
    def __init__(self, window_size):
        self.buffer = ""
        self.window_size = window_size
        self.position = 0
        self.blocks = []

    def feed_string(self, s):
        self.buffer += s
        while len(self.buffer) >= self.window_size:
            block = self.buffer[0:self.window_size]
            block_sha256 = sha256(block)
            #rs = RollingChecksum(self.window_size)
            #for c in block:
            #    rs.feed_byte(ord(c))
            #rs_ok = rs.value()
            rs_fast = RsyncRolling(self.window_size, block).value()
            self.blocks.append((self.position, rs_fast, block_sha256))
            self.position += self.window_size
            self.buffer = self.buffer[self.window_size:]
            

class RollingChecksum:
    def __init__(self, window_size):
        self.buffer = []
        self.window_size = window_size
        self.position = 0
        self.algo = RsyncRolling(window_size)

    def feed_string(self, s):
        for c in s:
            self.feed_byte(ord(c))

    def feed_byte(self, b):
        #assert type(b) == int and b <= 255 and b >= 0
        self.buffer.append(b)
        if len(self.buffer) == self.window_size + 1:
            self.algo.update(self.buffer[0], b)
            self.position += 1
            self.buffer.pop(0)
        elif len(self.buffer) < self.window_size: 
            self.algo.update(None, b)
        elif len(self.buffer) == self.window_size: 
            self.algo.update(None, b)
        else:
            assert False, "Unexpected buffer size"

    def value(self):
        if len(self.buffer) < self.window_size:
            return None
        else:
            return self.algo.value()

    def offset(self):
        return self.position

    def sha256(self):
        assert len(self.buffer) == self.window_size
        data = "".join(map(chr, self.buffer))
        return sha256(data)


def self_test():
    rs = RollingChecksum(3)
    result = []
    for c in (0,1,2,3,0,1,2,3):
        rs.feed_byte(c)
        result.append(rs.value())
    print result
"""
    assert result == [None, None, (0, 6), (1, 9), (2, 12), (3, 15), (4, 18), (5, 21), (6, 24)]

    rs = RollingChecksum(3)
    result = []
    for b in  range(1,10):
        result.append(rs.feed_byte(b))
    assert result == [None, None, (0, 6), (1, 9), (2, 12), (3, 15), (4, 18), (5, 21), (6, 24)]

    bs = BlockChecksum(3)
    bs.feed_string("".join([chr(x) for x in range(1,10)]))
    assert bs.blocks == [(0, 6, '039058c6f2c0cb492c533b0a4d14ef77cc0f78abccced5287d84a1a2011cfb81'), 
                         (3, 15, '787c798e39a5bc1910355bae6d0cd87a36b2e10fd0202a83e3bb6b005da83472'), 
                         (6, 24, '66a6757151f8ee55db127716c7e3dce0be8074b64e20eda542e5c1e46ca9c41e')]
"""

# Algorithm from http://tutorials.jenkov.com/rsync/checksums.html
class RsyncRolling:
    def __init__(self, window_size, initial_data = None):
        self.window_size = window_size
        self.a = 0
        self.b = 0
        if initial_data != None:
            assert len(initial_data) == window_size
            self.a = sum(map(ord, initial_data))
            for n in range(0, self.window_size):
                self.b += (window_size - n) * ord(initial_data[n])

    def update(self, remove, add):
        if remove == None:
            remove = 0
        self.a -= remove
        self.a += add
        self.b -= self.window_size * remove
        self.b += self.a

    def value(self):
        return self.a * self.b


class SimpleSumRolling:
    def __init__(self):
        self.sum = 0

    def update(self, remove, add):
        self.sum += add
        if remove != None:
            self.sum -= remove    
        return self.sum

    def value(self):
        return self.sum

self_test()


"""
import sys
rs = RollingChecksum(100)
for block in file_reader(sys.stdin):
    print len(block)
    rs.feed_string(block)
"""
