# -*- coding: utf-8 -*-
# Copyright 2013 Mats Ekberg
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

cdef extern from "rollsum.h":
    cdef struct _RollingState:
        pass
    ctypedef _RollingState RollingState
    RollingState init_rolling()
    int is_full(RollingState* state)
    int is_empty(RollingState* state)
    int push_rolling(RollingState* state, unsigned char c_add)

cdef extern from "intset.h":
    cdef struct _IntSet:
        pass
    ctypedef _IntSet IntSet
    IntSet* create_intset(int bucket_count)
    void add_intset(IntSet* intset, int int_to_add)
    int contains_intset(IntSet* intset, int int_to_find)
    void destroy_intset(IntSet* intset)

cdef class RollingChecksum:
    cdef RollingState state
    cdef IntSet* intset
    cdef int file_offset

    def __init__(self):
        self.state = init_rolling()
        self.intset = create_intset(100000)
        self.file_offset = 0

    def add_needles(self, s):
        cdef int n
        for n in s:
            add_intset(self.intset, n)

    def feed_string(self, s):
        cdef int rolling_value
        hits = []
        for c in s:
            rolling_value = self.feed_byte(ord(c))
            if contains_intset(self.intset, rolling_value):
                hits.append(self.file_offset - 1)
        return hits

    cpdef int feed_byte(RollingChecksum self, unsigned char b):
        self.file_offset += 1
        return push_rolling(&self.state, b)

    def value(self):
        pass

cpdef unsigned calc_rolling(char[] s):
    """ Convenience method to calculate the rolling checksum on a
    block."""
    cdef RollingState state
    state = init_rolling()
    cdef unsigned result
    result = 0
    for c in s:
        result = push_rolling(&state, c)
    return result

def benchmark():
    rs = RollingChecksum()
    for c in xrange(0, 10**7):
        rs.feed_byte(ord("a"))
