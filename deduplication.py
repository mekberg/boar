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

class RollingChecksum:
    def __init__(self, window_size):
        self.sum = 0
        self.buffer = []
        self.window_size = window_size
        self.position = 0

    def feed_string(self, s):
        for c in s:
            yield self.feed_byte(ord(c))

    def feed_byte(self, b):
        assert type(b) == int and b <= 255 and b >= 0
        self.buffer.append(b)
        self.sum += b
        if len(self.buffer) == self.window_size + 1:
            self.sum -= self.buffer[-self.window_size]
            self.position += 1
            self.buffer.pop(0)
            result = self.position, self.sum
        elif len(self.buffer) < self.window_size: 
            result = None
        elif len(self.buffer) == self.window_size: 
            result = self.position, self.sum
        else:
            assert False, "Unexpected buffer size"
        return result

def self_test():
    rs = RollingChecksum(3)
    result = list(rs.feed_string([chr(x) for x in range(1,10)]))
    assert result == [None, None, (0, 6), (1, 8), (2, 10), (3, 12), (4, 14), (5, 16), (6, 18)]

self_test()

"""
import sys
rs = RollingChecksum(100)
for block in file_reader(sys.stdin):
    print len(block)
    rs.feed_string(block)
"""
