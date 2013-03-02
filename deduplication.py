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
from jsonrpc import FileDataSource

import sys
from rollingcs import RollingChecksum, calc_rolling
import tempfile

class BlockChecksum:
    def __init__(self, window_size, tmpdir = None):
        self.buffer = FileAsString(tempfile.SpooledTemporaryFile(max_size=2**23, dir=tmpdir))
        self.window_size = window_size
        self.position = 0
        self.blocks = []

    def feed_string(self, s):
        self.buffer.append(s)
        while len(self.buffer) - self.position >= self.window_size:
            block = self.buffer[self.position:self.position+self.window_size]
            block_md5 = md5sum(block)
            block_rolling = calc_rolling(block, self.window_size)
            self.blocks.append((self.position, block_rolling, block_md5))
            self.position += self.window_size

    def harvest(self):
        result = self.blocks
        self.blocks = []
        return result
            
class UniformBlobGetter:
    def __init__(self, repo, local_blob_dir = None):
        self.repo = repo
        self.local_blob_dir = local_blob_dir

    def get_blob_size(self, blob_name):
        assert is_md5sum(blob_name)
        if self.local_blob_dir:
            local_path = os.path.join(self.local_blob_dir, blob_name)
            if os.path.exists(local_path):
                return long(os.path.getsize(local_path))
        return self.front.get_blob_size(blob_name)

    def get_blob_reader(self, blob_name, offset, size):
        assert is_md5sum(blob_name)
        if self.local_blob_dir:
            local_path = os.path.join(self.local_blob_dir, blob_name)
            if os.path.exists(local_path):
                fo = safe_open(local_path, "rb")
                fo.seek(offset)                
                return FileDataSource(fo, size)
        return self.repo.get_blob_reader(blob_name, offset, size)

class TailBuffer:
    """ A buffer that only physically keeps the last tail_size bytes
    of the data that is appended to it, but can be accessed using the
    positions of the original data. """

    def __init__(self, tail_size, tmpdir = None):
        #self.tail_size = tail_size
        self.tmpfo = tempfile.SpooledTemporaryFile(max_size=2**23, dir = tmpdir)
        self.buffer = FileAsString(self.tmpfo)
        
    def append(self, s):
        self.buffer.append(s)

    def get_blocks(self, start, size):
        assert False
        return file_reader(self.tmpfo, start, start + size)

    def __len__(self):
        return len(self.buffer)

    def __getitem__(self, index):
        return self.buffer.__getitem__(index)

class OriginalPieceHandler:
    def init_piece(self, index):
        pass

    def add_piece_data(self, index, data):
        pass
    
    def end_piece(self, index):
        # This method must return a tuple of (blob, offset). Those
        # values will be used for this piece in the recipe.
        pass

from statemachine import GenericStateMachine

START_STATE = "START"
ORIGINAL_STATE = "ORIGINAL"
DEDUP_STATE = "MATCH"
END_STATE = "END"

ORIGINAL_DATA_FOUND_EVENT = "ORIGINAL_EVENT"
DEDUP_BLOCK_FOUND_EVENT = "DEDUP_BLOCK_FOUND_EVENT"
EOF_EVENT = "EOF_EVENT"

class RecipeFinder(GenericStateMachine):
    def __init__(self, blocksdb, block_size, intset, __unused_blobsource_, original_piece_handler, tmpdir = None):
        GenericStateMachine.__init__(self)

        # State machine init
        self.add_state(START_STATE)
        self.add_state(ORIGINAL_STATE)
        self.add_state(DEDUP_STATE)
        self.add_state(END_STATE)

        self.add_event(ORIGINAL_DATA_FOUND_EVENT)
        self.add_event(DEDUP_BLOCK_FOUND_EVENT)
        self.add_event(EOF_EVENT)

        self.add_transition(START_STATE, ORIGINAL_DATA_FOUND_EVENT, ORIGINAL_STATE)
        self.add_transition(START_STATE, DEDUP_BLOCK_FOUND_EVENT, DEDUP_STATE)

        self.add_transition(ORIGINAL_STATE, ORIGINAL_DATA_FOUND_EVENT, ORIGINAL_STATE)
        self.add_transition(DEDUP_STATE, DEDUP_BLOCK_FOUND_EVENT, DEDUP_STATE)

        self.add_transition(ORIGINAL_STATE, DEDUP_BLOCK_FOUND_EVENT, DEDUP_STATE)
        self.add_transition(DEDUP_STATE, ORIGINAL_DATA_FOUND_EVENT, ORIGINAL_STATE)

        self.add_transition(ORIGINAL_STATE, EOF_EVENT, END_STATE)
        self.add_transition(DEDUP_STATE, EOF_EVENT, END_STATE)
        self.add_transition(START_STATE, EOF_EVENT, END_STATE)

        self.last_seen_offset = 0
        def assert_offset_ok(**args):
            assert self.last_seen_offset <= args['offset'], args['offset']
            self.last_seen_offset = args['offset']
        self.add_exit_handler(START_STATE, assert_offset_ok)
        self.add_exit_handler(ORIGINAL_STATE, assert_offset_ok)
        self.add_exit_handler(DEDUP_STATE, assert_offset_ok)
        
        self.add_transition_handler(START_STATE, ORIGINAL_DATA_FOUND_EVENT, ORIGINAL_STATE, 
                                    self.__on_original_data_start)
        self.add_transition_handler(DEDUP_STATE, ORIGINAL_DATA_FOUND_EVENT, ORIGINAL_STATE, 
                                    self.__on_original_data_start)
        self.add_transition_handler(ORIGINAL_STATE, EOF_EVENT, END_STATE, 
                                    self.__on_original_data_end)
        self.add_transition_handler(ORIGINAL_STATE, DEDUP_BLOCK_FOUND_EVENT, DEDUP_STATE, 
                                    self.__on_original_data_end)
        self.add_transition_handler(START_STATE, DEDUP_BLOCK_FOUND_EVENT, DEDUP_STATE, 
                                    self.__on_dedup_data_start)
        self.add_transition_handler(ORIGINAL_STATE, DEDUP_BLOCK_FOUND_EVENT, DEDUP_STATE, 
                                    self.__on_dedup_data_start)
        self.add_transition_handler(DEDUP_STATE, ORIGINAL_DATA_FOUND_EVENT, ORIGINAL_STATE, 
                                    self.__on_dedup_data_end)
        self.add_transition_handler(DEDUP_STATE, EOF_EVENT, END_STATE, 
                                    self.__on_dedup_data_end)

        self.add_enter_handler(DEDUP_STATE, self.__on_dedup_block)
        self.add_exit_handler(ORIGINAL_STATE, self.__on_original_data_part_end)

        self.add_enter_handler(END_STATE, self.__on_end_of_file)
        self.start(START_STATE)

        self.blocksdb = blocksdb
        self.block_size = block_size
        self.rs = RollingChecksum(block_size, intset)
        self.original_piece_handler = original_piece_handler

        self.tail_buffer = TailBuffer(self.block_size*2, tmpdir = tmpdir)
        self.end_of_last_hit = 0 # The end of the last matched block
        self.md5summer = hashlib.md5()
        self.restored_md5summer = hashlib.md5()

        self.closed = False
        self.feed_byte_count = 0

        self.sequences = []
        self.seq_number = -1
        self.recipe = None

    def __on_original_data_start(self, **args):
        self.original_start = args['offset']
        self.last_flush_end = args['offset']
        self.seq_number += 1
        self.original_piece_handler.init_piece(self.seq_number)

    def __on_original_data_part_end(self, **args):
        data = self.tail_buffer[self.last_flush_end : args['offset']]
        self.last_flush_end = args['offset']
        self.end_of_last_hit = args['offset']
        self.original_piece_handler.add_piece_data(self.seq_number, data)
        self.restored_md5summer.update(data)
        #print "Flushing", len(data), "bytes of original data"

    def __on_original_data_end(self, **args):
        size = args['offset'] - self.original_start
        del self.original_start
        del self.last_flush_end
        blob, blob_offset = self.original_piece_handler.end_piece(self.seq_number)
        self.sequences.append(Struct(blob=blob, blob_offset=blob_offset, size=size))

    def __on_dedup_data_start(self, **args):
        self.seq_number += 1
        self.sequences.append([])

    def __on_dedup_block(self, **args):
        self.sequences[-1].append(args['md5'])
        data = self.tail_buffer[args['offset']: args['offset'] + self.block_size] # TODO: use args['block_data'] in production
        self.end_of_last_hit = args['offset'] + self.block_size
        self.restored_md5summer.update(data)
        assert md5sum(data) == args['md5'] # TODO: remove in production
        assert args['md5'] == md5sum(args['block_data'])
        

    def __on_dedup_data_end(self, **args):
        pass

    def __on_end_of_file(self, **args):
        pass

    def feed(self, s):
        #print "Feeding", len(s), "bytes"
        assert not self.closed
        self.feed_byte_count += len(s)
        self.rs.feed_string(s)
        self.md5summer.update(s)
        self.tail_buffer.append(s)
        for offset, rolling in self.rs:
            if offset < self.end_of_last_hit:
                # Ignore overlapping blocks
                continue
            block_data = self.tail_buffer[offset : offset + self.block_size]
            md5 = md5sum(block_data)
            self.end_of_last_hit >= 0
            if self.blocksdb.has_block(md5):
                assert self.end_of_last_hit >= 0
                if offset - self.end_of_last_hit > 0:
                    # If this hit is NOT a continuation of the last
                    # one, there must be original data in between.
                    #print "Gap found between block hits"
                    self.dispatch(ORIGINAL_DATA_FOUND_EVENT, offset = self.end_of_last_hit)
                self.dispatch(DEDUP_BLOCK_FOUND_EVENT, md5 = md5, offset = offset, block_data = block_data)

        #print "State after feeding is", self.get_state()
        # We know here that all data, except the last block_size
        # bytes (which may still be part of a hit when we feed
        # more data), are original. Let's tell the state machine
        # that. By doing this, we chop up the sequence, as opposed
        # to just doing one unpredictably huge sequence at the
        # end.
        # print "Half-time flush!"
        if self.end_of_last_hit < self.feed_byte_count - self.block_size:
            # print "Last hit leaves a gap - state is", self.get_state()
            if self.get_state() != ORIGINAL_STATE:
                self.dispatch(ORIGINAL_DATA_FOUND_EVENT, offset = self.end_of_last_hit)
            #print "Before flush:", self.get_state()
            self.dispatch(ORIGINAL_DATA_FOUND_EVENT, offset = self.feed_byte_count - self.block_size)
        #print "Half-time flush complete"

    def close(self):
        #print "Closing"
        assert not self.closed
        self.closed = True
        if self.end_of_last_hit != self.feed_byte_count:
            offset = max(self.feed_byte_count - self.block_size, self.end_of_last_hit)
            self.dispatch(ORIGINAL_DATA_FOUND_EVENT, offset = offset)
        self.dispatch(EOF_EVENT,offset = self.feed_byte_count)
        assert len(self.tail_buffer) == self.feed_byte_count
        assert self.get_state() == END_STATE
        assert self.restored_md5summer.hexdigest() == self.md5summer.hexdigest()
        #print_recipe(self.get_recipe())
        restored_size = 0
        for piece in self.get_recipe()['pieces']:
            restored_size += piece['size']
        assert restored_size == self.feed_byte_count, "Restored is %s, feeded is %s" % (restored_size, self.feed_byte_count)
        del self.rs

    def seq2rec(self):
        restored_size = 0
        for s in self.sequences:
            if isinstance(s, Struct):
                restored_size += s.size
                yield {"source": s.blob,
                       "offset": s.blob_offset,
                       "size": s.size,
                       "original": True,
                       "repeat": 1}
            elif type(s) == list:
                assert s
                seqfinder = self.blocksdb.get_sequence_finder()
                for md5 in s:
                    if not seqfinder.can_add(md5):
                        blob, offset, size = seqfinder.get_matches().next()
                        restored_size += size
                        yield {"source": blob,
                               "offset": offset,
                               "size": size,
                               "original": False,
                               "repeat": 1}
                        seqfinder = self.blocksdb.get_sequence_finder()
                    seqfinder.add_block(md5)
                matches = list(seqfinder.get_matches()) # We only need one
                if matches:
                    blob, offset, size = matches[0]
                    restored_size += size
                    yield {"source": blob,
                       "offset": offset,
                       "size": size,
                       "original": False,
                       "repeat": 1}
            else:
                assert False, s
        assert restored_size == self.feed_byte_count

    def get_recipe(self):
        assert self.closed
        if self.recipe == None:
            self.recipe = {"method": "concat",
                           "md5sum": self.md5summer.hexdigest(),
                           "size": len(self.tail_buffer),
                           "pieces": list(self.seq2rec())}
        return self.recipe
            
def print_recipe(recipe):
    print "Md5sum:", recipe["md5sum"]
    print "Size  :", recipe["size"]
    print "Method:", recipe['method']
    print "Pieces:", len(recipe['pieces'])
    pos = 0
    dedup_size = 0
    for p in recipe['pieces']:
        print "  Original     :", p['original']
        print "  Source blob  :", p['source'] if p['source'] else "SELF"
        print "  Source offset:", p['offset']
        print "  Size         :", p['size']
        print "  Position     : %s - %s" % (hex(pos), hex(pos + p['size'] * p.get('repeat', 1)))
        print "  Repeat       :", p.get('repeat', "(1)")
        print "  ---------------"
        pos += p['size']
        if p['source'] == None: # Count the parts we couldn't find elsewhere
            dedup_size += p['size']
    try:
        print "Dedup removed %s%% of original size" % round((100.0 * (1.0 - float(dedup_size) / recipe["size"])), 1)
    except ZeroDivisionError:
        print "Zero size recipe"
        pass

def benchmark():
    import time
    b = BlockChecksum(2**16)
    data = "x" * 12345
    t0 = time.time()
    for n in range(0,10000):
        b.feed_string(data)
        b.harvest()
    print time.time() - t0

#res=cProfile.run('main()', "prof.txt")
#import pstats
#p = pstats.Stats('prof.txt')
#p.sort_stats('cum').print_stats(20)
#sys.exit(res)

def main():
    import cProfile, pstats
    res=cProfile.run('benchmark()', "deduplication_prof.txt")
    p = pstats.Stats('deduplication_prof.txt')
    p.sort_stats('cum').print_stats(20)

#main()
#benchmark()

