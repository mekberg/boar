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

__version__ = "1.0" # Major, minor. Major == API changes

from libc.stdint cimport uint32_t, uint64_t

cdef extern from "rollsum.h":
    cdef struct _RollingState:
        pass
    ctypedef _RollingState RollingState
    RollingState* create_rolling(int window_size)
    void destroy_rolling(RollingState* state)
    int is_full(RollingState* state)
    int is_empty(RollingState* state)
    void push_rolling(RollingState* state, unsigned char c_add)
    void push_buffer_rolling(RollingState* state, char* buf, unsigned len)
    uint64_t value64_rolling(RollingState* state)

cdef extern from "intset.h":
    cdef struct _IntSet:
        pass
    ctypedef _IntSet IntSet
    IntSet* create_intset(int bucket_count)
    void add_intset(IntSet* intset, int int_to_add)
    int contains_intset(IntSet* intset, int int_to_find)
    void destroy_intset(IntSet* intset)

cdef extern from "blocksdb.h":

    cdef enum BLOCKSDB_RESULT:
        BLOCKSDB_DONE=1
        BLOCKSDB_ROW
        BLOCKSDB_ERR_CORRUPT
        BLOCKSDB_ERR_OTHER

    BLOCKSDB_RESULT init_blocksdb(const char* dbfile, int block_size, void** out_handle)
    BLOCKSDB_RESULT close_blocksdb(void* handle)

    BLOCKSDB_RESULT add_block(void* handle, const char* blob, uint64_t offset, const char* md5)
    BLOCKSDB_RESULT add_rolling(void* handle, uint64_t rolling)

    BLOCKSDB_RESULT get_rolling_init(void* handle)
    BLOCKSDB_RESULT get_rolling_next(void* handle, uint64_t* rolling)
    BLOCKSDB_RESULT get_rolling_finish(void* handle)

    BLOCKSDB_RESULT get_blocks_init(void* handle, char* md5, int limit)
    BLOCKSDB_RESULT get_blocks_next(void* handle, char* blob, uint64_t* offset)
    BLOCKSDB_RESULT get_blocks_finish(void *handle)

    BLOCKSDB_RESULT delete_blocks_init(void* dbstate)
    BLOCKSDB_RESULT delete_blocks_add(void* dbstate, char* blob)
    BLOCKSDB_RESULT delete_blocks_finish(void* dbstate)

    BLOCKSDB_RESULT get_modcount(void* handle, int* out_modcount)
    BLOCKSDB_RESULT increment_modcount(void* handle)

    BLOCKSDB_RESULT get_block_size(void* dbstate, int* out_block_size)

    BLOCKSDB_RESULT begin_blocksdb(void* handle)
    BLOCKSDB_RESULT commit_blocksdb(void* handle)
    
    char* get_error_message(void* handle)
    
#class BlocksDB:
    

cdef class IntegerSet:
    cdef IntSet* intset

    def __cinit__(self):
        self.intset = NULL
   
    def __init__(self, bucket_count):
        adjusted_bucket_count = 1
        while adjusted_bucket_count < bucket_count:
            adjusted_bucket_count *= 2
        self.intset = create_intset(adjusted_bucket_count)

    def __dealloc__(self):
        if self.intset != NULL:
            destroy_intset(self.intset)

    def add(self, uint64_t int_to_add):
        add_intset(self.intset, int_to_add)
    
    def add_all(self, ints_to_add):
        cdef uint64_t n
        for n in ints_to_add:
            self.add(n)

    def contains(self, uint64_t int_to_find):
        return bool(contains_intset(self.intset, int_to_find))

    cdef IntSet* get_intset(self):
        return self.intset

cdef class RollingChecksum:
    cdef RollingState* state
    cdef uint64_t feeded_bytecount
    cdef unsigned window_size

    cdef unsigned feed_pos
    cdef object   feed_queue
    cdef object   feed_s
    cdef IntegerSet my_intset

    def __init__(self, int window_size, m_intset):
        self.state = create_rolling(window_size)
        assert self.state, "Create_rolling returned None"
        assert m_intset, "Intset must not be None"
        self.my_intset = m_intset
        self.feeded_bytecount = 0
        self.window_size = window_size

        self.feed_queue = []
        self.feed_pos = 0
        self.feed_s = ""

    def __cinit__(self):
        self.state = NULL

    def __dealloc__(self):
        if self.state != NULL:
            destroy_rolling(self.state)

    def feed_string(self, s):
        self.feed_queue.append(s)
        #print "Feed queue length:", len(self.feed_queue)

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
        cdef uint64_t rolling_value
        cdef char* buf
        cdef unsigned int buf_len
        cdef IntSet* intset
        while True: # Until StopIteration or a hit is returned
            if self.feed_pos == len(self.feed_s):
                self._pop_queue()
            buf = self.feed_s
            buf_len = len(self.feed_s)
            intset = self.my_intset.get_intset()
            while self.feed_pos < buf_len:
                push_rolling(self.state, buf[self.feed_pos])
                self.feeded_bytecount += 1
                self.feed_pos += 1
                if self.feeded_bytecount >= self.window_size:
                    rolling_value = value64_rolling(self.state)
                    if contains_intset(intset, rolling_value):
                        return (self.feeded_bytecount - self.window_size, rolling_value)

    cpdef uint64_t value(self):
        try:
            while True:
                self.next()
        except StopIteration:
            return value64_rolling(self.state)

cpdef uint64_t calc_rolling(s, window_size):
    """ Convenience method to calculate the rolling checksum on a
    block."""
    assert len(s) <= window_size
    return _calc_rolling(s, len(s), window_size)

cdef uint64_t _calc_rolling(char[] buf, unsigned buf_length, unsigned window_size):
    cdef RollingState* state 
    cdef uint64_t result
    state = create_rolling(window_size)
    #for n in xrange(0, buf_length):
    #    push_rolling(state, buf[n])
    push_buffer_rolling(state, buf, buf_length)
    result = value64_rolling(state)
    destroy_rolling(state)
    return result;

def benchmark():
    import random
    sw = StopWatch()
    randints = [random.randint(0, 2**32-1) for n in range(1000000)]
    intset = IntegerSet(len(randints))
    print len(randints), randints[0:10]
    intset.add_all(randints)
    del randints
    rs = RollingChecksum(65000, intset)
    sw.mark("Setup")
    s = "a" * 4096
    for c in xrange(0, 10000):
        rs.feed_string(s)
        for result in rs:
            pass
    print "Feeded", rs.feeded_bytecount, "bytes"
    sw.mark("Feeding")

def test_string(window_size, ls, ss):
    rs = RollingChecksum(window_size, IntegerSet(100))
    rs.feed_string(ls)
    rolling_rs1 = rs.value()

    rs = RollingChecksum(window_size, IntegerSet(100))
    rs.feed_string(ss)
    rolling_rs2 = rs.value()

    rolling_cr = calc_rolling(ss, window_size)
    #print rolling_rs1, rolling_rs2, rolling_cr
    assert rolling_rs1 == rolling_rs2 == rolling_cr
    return rolling_rs1

def self_test():
    assert test_string(3, "xyzabc", "abc") == 50594179
    assert test_string(3, "abc", "abc") == 50594179
    assert test_string(3, "qabc", "abc") == 50594179
    assert test_string(3, "", "") == 0

    rs = RollingChecksum(3, IntegerSet(100))
    rs.feed_string("a")
    rs.feed_string("b")
    rs.feed_string("c")
    assert rs.value() == 50594179


    intset = IntegerSet(100)
    rs = RollingChecksum(3, intset)
    intset.add_all([25231617, 50594179, 50987398, 51380617])
    rs.feed_string("a")
    rs.feed_string("b")
    rs.feed_string("c")
    rs.feed_string("d")
    rs.feed_string("e")
    result = list(rs)
    assert result == [(0L, 50594179L), (1L, 50987398L), (2L, 51380617L)], result

    #big_string = chr(255) * 10**6 # 10 MB
    #assert test_string(10**6, big_string, big_string)
    #print "Self test completed"

import time
class StopWatch:
    def __init__(self):
        self.t_init = time.time()
        self.t_last = time.time()

    def mark(self, msg):
        now = time.time()
        print "MARK: %s %s (total %s)" % ( msg, now - self.t_last, now - self.t_init )
        self.t_last = time.time()

cdef class BlocksDB:
   cdef void* dbhandle
   cdef int in_transaction
   cdef IntegerSet all_rolling
   cdef int is_modified
   cdef int last_seen_modcount
   cdef int __rolling_loaded

   def __init__(self, dbfile, block_size):
       assert type(block_size) == int, "illegal argument: block_size must be an integer"
       dbfile_utf8 = dbfile.encode("utf-8")
       result = init_blocksdb(dbfile_utf8, block_size, &self.dbhandle)
       if result != BLOCKSDB_DONE:
           raise Exception(get_error_message(self.dbhandle))
       self.in_transaction = False
       self.is_modified = False
       self.last_seen_modcount = -1
       self.__rolling_loaded = False # Lazy initialization

   def __load_rolling_lazy(self):
       if self.__rolling_loaded:
           return
       self.__rolling_loaded = True
       self.__reload_rolling()

   def __cinit__(self):
       self.dbhandle = NULL

   def __dealloc__(self):
       if self.dbhandle != NULL:
           close_blocksdb(self.dbhandle)
   
   def __reload_rolling(self):
       rolling = self.get_all_rolling()
       self.all_rolling = IntegerSet(max(len(rolling), 2**16))
       self.all_rolling.add_all(rolling)

       # This is not transaction safe unless we're in a transaction -
       # it is possible some commit went through since we finished
       # reading the values, but let's not push the issue, the
       # consequences are slight.
       result = get_modcount(self.dbhandle, &self.last_seen_modcount)
       if result != BLOCKSDB_DONE:
           raise Exception(get_error_message(self.dbhandle))

   def get_all_rolling(self):
        self.__load_rolling_lazy()
        result = []
        if get_rolling_init(self.dbhandle) != BLOCKSDB_DONE:
            raise Exception(get_error_message(self.dbhandle))
        cdef uint64_t rolling
        while True:
            s = get_rolling_next(self.dbhandle, &rolling)
            if s == BLOCKSDB_ROW:
                result.append(rolling)
            elif s == BLOCKSDB_DONE:
                break
            else:
                raise Exception(get_error_message(self.dbhandle))
        if get_rolling_finish(self.dbhandle) != BLOCKSDB_DONE:
            raise Exception(get_error_message(self.dbhandle))
        return result

   def has_block(self, md5):
       return bool(self.get_block_locations(md5, limit = 1))

   def get_block_locations(self, md5, limit = -1):
        result = []
        if BLOCKSDB_DONE != get_blocks_init(self.dbhandle, md5, limit):
            raise Exception(get_error_message(self.dbhandle))
        cdef char blob[33]
        cdef uint64_t offset
        while True:
            s = get_blocks_next(self.dbhandle, blob, &offset)
            if s == BLOCKSDB_ROW:
                blob[32] = 0
                result.append((blob, offset))
            elif s == BLOCKSDB_DONE:
                break
            else:
                raise Exception(get_error_message(self.dbhandle))            
        if BLOCKSDB_DONE != get_blocks_finish(self.dbhandle):
            raise Exception(get_error_message(self.dbhandle))
        return result

   def add_rolling(self, rolling):
       self.__load_rolling_lazy()
       assert self.in_transaction, "Tried to add a rolling cs outside of a transaction"
       if not self.all_rolling.contains(rolling):
           self.all_rolling.add(rolling)
           self.is_modified = True
           result = add_rolling(self.dbhandle, rolling)
           if result != BLOCKSDB_DONE:
               raise Exception(get_error_message(self.dbhandle))

   def delete_blocks(self, blobs):
       #print "Deleting blocks belonging to blobs", blobs
       assert self.in_transaction, "Tried to delete blocks outside of a transaction"
       if BLOCKSDB_DONE != delete_blocks_init(self.dbhandle):
           raise Exception(get_error_message(self.dbhandle))

       for blob in blobs:
           if BLOCKSDB_DONE != delete_blocks_add(self.dbhandle, blob):
               raise Exception(get_error_message(self.dbhandle))

       if BLOCKSDB_DONE != delete_blocks_finish(self.dbhandle):
           raise Exception(get_error_message(self.dbhandle))
           

   def add_block(self, blob, offset, md5):
       assert self.in_transaction, "Tried to add a block outside of a transaction"       
       result = add_block(self.dbhandle, blob, offset, md5)
       if result != BLOCKSDB_DONE:
           raise Exception(get_error_message(self.dbhandle))
       self.is_modified = True
       
   def begin(self):
       self.__load_rolling_lazy()
       assert not self.in_transaction, "Tried to start a transaction while one was already in progress"
       result = begin_blocksdb(self.dbhandle)
       if result != BLOCKSDB_DONE:
           raise Exception(get_error_message(self.dbhandle))
       cdef int current_modcount
       result = get_modcount(self.dbhandle, &current_modcount)
       if self.last_seen_modcount != current_modcount:
           self.__reload_rolling()
       self.in_transaction = True

   def commit(self):
       assert self.in_transaction, "Tried to a commit while no transaction was in progress"
       self.in_transaction = False
       if self.is_modified:
           result = increment_modcount(self.dbhandle)
           if result != BLOCKSDB_DONE:
               raise Exception(get_error_message(self.dbhandle))
           self.is_modified = False
       result = get_modcount(self.dbhandle, &self.last_seen_modcount)
       if result != BLOCKSDB_DONE:
           raise Exception(get_error_message(self.dbhandle))

       result = commit_blocksdb(self.dbhandle)
       if result != BLOCKSDB_DONE:
           raise Exception(get_error_message(self.dbhandle))

   def get_block_size(self):
       cdef int block_size
       result = get_block_size(self.dbhandle, &block_size)
       if result != BLOCKSDB_DONE:
           raise Exception(get_error_message(self.dbhandle))
       return block_size
       

def test_blocksdb_class():
    db = BlocksDB("testdb.sqlite")
    print db.get_all_rolling()
    print db.get_all_blocks("d41d8cd98f00b204e9800998ecf8427e")
    db.begin()
    db.add_rolling(12345)
    db.commit()

#def test_blocksdb():
    #print "Running"
    #blocksdb = init_blocksdb()
    #add_block(blocksdb, "dummy1", 666, "d41d8cd98f00b204e9800998ecf8427e")
    #add_block(blocksdb, "dummy2", 666, "d41d8cd98f00b204e9800998ecf8427e")
    #add_rolling(blocksdb, 17)
    #print "Done"
    
    
    
    
    
#self_test()
#benchmark()


#test_blocksdb_class()
