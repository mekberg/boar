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
    RollingState* create_rolling(int window_size)
    void destroy_rolling(RollingState* state)
    int is_full(RollingState* state)
    int is_empty(RollingState* state)
    void push_rolling(RollingState* state, unsigned char c_add)
    int value_rolling(RollingState* state)

cdef extern from "intset.h":
    cdef struct _IntSet:
        pass
    ctypedef _IntSet IntSet
    IntSet* create_intset(int bucket_count)
    void add_intset(IntSet* intset, int int_to_add)
    int contains_intset(IntSet* intset, int int_to_find)
    void destroy_intset(IntSet* intset)

cdef class RollingChecksum:
    cdef RollingState* state
    cdef IntSet* intset
    cdef int feeded_bytecount
    cdef unsigned window_size

    cdef unsigned feed_pos
    cdef object   feed_queue
    cdef object   feed_s

    def __init__(self, int window_size):
        self.state = create_rolling(window_size)
        self.intset = create_intset(100000)
        self.feeded_bytecount = 0
        self.window_size = window_size

        self.feed_queue = []
        self.feed_pos = 0
        self.feed_s = ""

    def __dealloc__(self):
        destroy_rolling(self.state)
        destroy_intset(self.intset)

    def add_needles(self, s):
        cdef unsigned n
        for n in s:
            add_intset(self.intset, n)

    def feed_string(self, s):
        self.feed_queue.append(s)

    cdef _pop_queue(self):
        assert self.feed_pos == len(self.feed_s)
        if not self.feed_queue:
            raise StopIteration
        s = self.feed_queue.pop(0)
        self.feed_s = s
        self.feed_pos = 0        

    def __iter__(self):
        return self

    def __next__(self):
        cdef unsigned rolling_value
        while True: # Until StopIteration or a hit is returned
            if self.feed_pos == len(self.feed_s):
                self._pop_queue()
            while self.feed_pos < len(self.feed_s):
                self._feed_byte(ord(self.feed_s[self.feed_pos]))
                self.feed_pos += 1
                if self.feeded_bytecount >= self.window_size:
                    rolling_value = value_rolling(self.state)
                    if contains_intset(self.intset, rolling_value):
                        return (self.feeded_bytecount - self.window_size, rolling_value)

    cpdef unsigned value(self):
        try:
            while True:
                self.next()
        except StopIteration:
            return value_rolling(self.state)

    cdef _feed_byte(RollingChecksum self, unsigned char b):
        self.feeded_bytecount += 1
        push_rolling(self.state, b)
        #print "Feeded", chr(b), self.feeded_bytecount, value_rolling(self.state)

cpdef unsigned calc_rolling(s, window_size):
    """ Convenience method to calculate the rolling checksum on a
    block."""
    assert len(s) <= window_size
    return _calc_rolling(s, len(s), window_size)

cdef unsigned _calc_rolling(char[] buf, unsigned buf_length, unsigned window_size):
    cdef RollingState* state 
    cdef int result
    state = create_rolling(window_size)
    for n in xrange(0, buf_length):
        push_rolling(state, buf[n])
    result = value_rolling(state)
    destroy_rolling(state)
    return result;

def benchmark():
    rs = RollingChecksum()
    for c in xrange(0, 10**7):
        rs._feed_byte(ord("a"))

def test_string(window_size, ls, ss):
    rs = RollingChecksum(window_size)
    rs.feed_string(ls)
    rolling_rs1 = rs.value()

    rs = RollingChecksum(window_size)
    rs.feed_string(ss)
    rolling_rs2 = rs.value()

    rolling_cr = calc_rolling(ss, window_size)
    print rolling_rs1, rolling_rs2, rolling_cr
    assert rolling_rs1 == rolling_rs2 == rolling_cr
    return rolling_rs1

def self_test():
    assert test_string(3, "xyzabc", "abc") == 50594179
    assert test_string(3, "abc", "abc") == 50594179
    assert test_string(3, "qabc", "abc") == 50594179
    assert test_string(3, "", "") == 0

    rs = RollingChecksum(3)
    rs.feed_string("a")
    rs.feed_string("b")
    rs.feed_string("c")
    assert rs.value() == 50594179


    rs = RollingChecksum(3)
    rs.add_needles([25231617, 50594179, 50987398, 51380617])
    rs.feed_string("a")
    rs.feed_string("b")
    rs.feed_string("c")
    rs.feed_string("d")
    rs.feed_string("e")
    assert list(rs) == [(0L, 50594179L), (1L, 50987398L), (2L, 51380617L)]

    #big_string = chr(255) * 10**6 # 10 MB
    #assert test_string(10**6, big_string, big_string)
self_test()
