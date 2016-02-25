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
from ordered_dict import OrderedDict
from jsonrpc import FileDataSource

import sys
import tempfile
import array

try:
    if os.getenv("BOAR_DISABLE_DEDUP") == "1": raise ImportError()
    import cdedup
    assert cdedup.__version__ == "1.0", "Unexpected deduplication module version (was: %s)" % rollingcs.__version__
    cdedup_version = cdedup.__version__
    from cdedup import RollingChecksum, calc_rolling, IntegerSet, BlocksDB
    dedup_available = True
except ImportError:
    cdedup_version = None
    dedup_available = False

def CreateIntegerSet(ints):
    """This method will return an IntegerSet containing the given
    ints. The IntegerSet is suitable for use with the RecipeFinder
    class. An IntegerSet created with this function should not be used
    for other purposes. Note that in case the c extension is
    unavailable (dedup_available == False), then a FakeIntegerSet
    instance will be returned instead."""
    # bucket count must be a power of two
    if dedup_available:
        intset = IntegerSet(max(len(ints), 100000))
    else:
        intset = FakeIntegerSet(len(ints))
    intset.add_all(ints)
    return intset

class FakeRollingChecksum:
    """This is a dummy version of RollingChecksum. An instance of this
    class will never report any hits."""
    def __init__(self, window_size, intset):
        pass

    def feed_string(self, s):
        pass

    def __iter__(self):
        return self

    def next(self):
        raise StopIteration()

class FakeIntegerSet:
    """This is a dummy version of IntegerSet. An instance of this
    class will always return False when contains() is called."""
    def __init__(self, bucket_count):
        pass

    def add_all(self, integers):
        pass
    
    def contains(self, n):
        return False

class FakeBlockChecksum:
    """This is a dummy version of BlockChecksum. An instance of this
    class will always return an empty list when harvest() is
    called."""
    def __init__(self, window_size):
        pass

    def feed_string(self, s):
        pass

    def harvest(self):
        return []

class TmpBlocksDB:
    def __init__(self, blocksdb):
        self.blocksdb = blocksdb
        self.blocks = {} # md5 -> [(blob, offset), ...]

    def add_tmp_block(self, md5, blob, offset):
        assert is_md5sum(md5)
        assert is_md5sum(blob)
        if md5 not in self.blocks:
            self.blocks[md5] = []
        self.blocks[md5].append((blob, offset))

    def get_block_size(self):
        return self.blocksdb.get_block_size()

    def get_block_locations(self, md5, limit = -1):
        return self.blocks.get(md5, []) + self.blocksdb.get_block_locations(md5, limit)

    def has_block(self, md5):
        return md5 in self.blocks or self.blocksdb.has_block(md5)

class FakeBlocksDB:
    def __init__(self, dbfile, block_size):
        self.block_size = block_size

    def get_all_rolling(self):
        return []

    def has_block(self, md5):
        return False

    def get_block_locations(self, md5, limit = -1):
        return []

    def add_rolling(self, rolling):
        pass

    def delete_blocks(self, blobs):
        pass

    def add_block(self, blob, offset, md5):
        pass

    def begin(self):
        pass

    def commit(self):
        pass

    def get_block_size(self):
        return self.block_size

    
    

class BlockChecksum:
    def __init__(self, window_size):
        self.buffer = TailBuffer()
        self.window_size = window_size
        self.position = 0
        self.blocks = []

    def feed_string(self, s):
        self.buffer.append(s)
        while self.buffer.virtual_size() - self.position >= self.window_size:
            block = self.buffer[self.position:self.position+self.window_size]
            block_md5 = md5sum(block)
            block_rolling = calc_rolling(block, self.window_size)
            self.blocks.append((self.position, block_rolling, block_md5))
            self.position += self.window_size
        self.buffer.release(self.position)

    def harvest(self):
        result = self.blocks
        self.blocks = []
        return result

if not dedup_available:
    del BlockChecksum

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
        return self.repo.get_blob_size(blob_name)

    def get_blob_reader(self, blob_name, offset, size):
        assert is_md5sum(blob_name)
        if self.local_blob_dir:
            local_path = os.path.join(self.local_blob_dir, blob_name)
            if os.path.exists(local_path):
                fo = safe_open(local_path, "rb")
                fo.seek(offset)                
                return FileDataSource(fo, size)
        return self.repo.get_blob_reader(blob_name, offset, size)

class OriginalPieceHandler:
    def init_piece(self, index):
        pass

    def add_piece_data(self, index, data):
        pass
    
    def end_piece(self, index):
        pass

    def close(self):
        pass

    def get_piece_address(self, index):
        """After the handler has been closed, this method must return
        a tuple of (blob, offset) for every piece that has been
        processed. Those values will be used for this piece in the
        recipe."""
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
    def __init__(self, blocksdb, block_size, intset, blob_source, original_piece_handler, tmpdir = None,
                 RollingChecksumClass = None):
        GenericStateMachine.__init__(self)

        self.blob_source = blob_source

        if not RollingChecksumClass:
            RollingChecksumClass = RollingChecksum

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
        self.add_transition_handler(START_STATE, EOF_EVENT, END_STATE,
                                    self.__on_original_data_start)
        self.add_transition_handler(START_STATE, EOF_EVENT, END_STATE,
                                    self.__on_original_data_end)
        self.add_enter_handler(DEDUP_STATE, self.__on_dedup_block)
        self.add_exit_handler(ORIGINAL_STATE, self.__on_original_data_part_end)

        self.add_enter_handler(END_STATE, self.__on_end_of_file)
        self.start(START_STATE)

        self.blocksdb = blocksdb
        self.block_size = block_size
        self.rs = RollingChecksumClass(block_size, intset)
        self.original_piece_handler = original_piece_handler

        self.tail_buffer = TailBuffer()
        self.end_of_last_hit = 0 # The end of the last matched block
        self.last_flush_end = 0
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
        #print args
        #print "Releasing ", self.last_flush_end
        self.tail_buffer.release(self.last_flush_end)
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
        self.original_piece_handler.end_piece(self.seq_number)
        self.sequences.append(Struct(piece_handler = self.original_piece_handler,
                                     piece_index = self.seq_number,
                                     piece_size = size))

    def __on_dedup_data_start(self, **args):
        self.seq_number += 1
        self.sequences.append([])

    def __on_dedup_block(self, **args):
        self.sequences[-1].append(args['md5'])
        self.end_of_last_hit = args['offset'] + self.block_size
        self.restored_md5summer.update(args['block_data'])

    def __on_dedup_data_end(self, **args):
        pass

    def __on_end_of_file(self, **args):
        pass

    def feed(self, s):
        #print "Feeding", len(s), "bytes"
        assert type(s) == str
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
        
        # TODO: This stuff should be moved to on_file_end()
        assert not self.closed
        self.closed = True
        if self.end_of_last_hit != self.feed_byte_count:
            offset = max(self.feed_byte_count - self.block_size, self.end_of_last_hit)
            self.dispatch(ORIGINAL_DATA_FOUND_EVENT, offset = offset)
        self.dispatch(EOF_EVENT,offset = self.feed_byte_count)
        assert self.tail_buffer.virtual_size() == self.feed_byte_count
        assert self.get_state() == END_STATE
        assert self.restored_md5summer.hexdigest() == self.md5summer.hexdigest()
        self.original_piece_handler.close()

        #print_recipe(self.get_recipe())
        restored_size = 0
        for piece in self.get_recipe()['pieces']:
            restored_size += piece['size'] * piece['repeat']
        assert restored_size == self.feed_byte_count, "Restored is %s, feeded is %s" % (restored_size, self.feed_byte_count)
        del self.rs
        

    def __seq2rec(self):
        restored_size = 0

        def get_dict(source, offset, size, original):
            #assert is_md5sum(source)
            assert offset >= 0 
            assert size >= 0
            assert type(original) == bool
            
            return OrderedDict([("source", source),
                                ("offset", offset),
                                ("size", size),
                                ("original", original),
                                ("repeat", 1)])

        for s in self.sequences:
            if isinstance(s, Struct):
                # Original data
                restored_size += s.piece_size
                blob, offset = s.piece_handler.get_piece_address(s.piece_index)
                yield get_dict(blob, offset, s.piece_size, True)

            elif type(s) == list:
                # Duplicated data
                assert s
                seqfinder = BlockSequenceFinder(self.blocksdb)
                for md5 in s:
                    if not seqfinder.can_add(md5):
                        blob, offset, size = seqfinder.get_matches().next()
                        restored_size += size
                        yield get_dict(blob, offset, size, False)
                        seqfinder = BlockSequenceFinder(self.blocksdb)
                    seqfinder.add_block(md5)
                matches = list(seqfinder.get_matches()) # We only need one
                if matches:
                    blob, offset, size = matches[0]
                    restored_size += size
                    yield get_dict(blob, offset, size, False)
            else:
                assert False, s
        assert restored_size == self.feed_byte_count

    def __polish_recipe_tail(self):
        assert self.recipe
        pieces = self.recipe['pieces']
        if len(pieces) < 2:
            return
        if not (pieces[-1]['original'] == True and pieces[-2]['original'] == False):
            return
        # The last piece is original, and the second to last piece is
        # not. It could be possible to extend the last hit all the way.
        blob = pieces[-2]['source']
        required_blob_size = pieces[-2]['offset'] + pieces[-2]['size'] + pieces[-1]['size']
        if self.blob_source.get_blob_size(blob) < required_blob_size:
            # Cannot possibly be a full hit
            return
        blob_start = pieces[-2]['offset'] + pieces[-2]['size']
        blob_read_size = pieces[-1]['size']
        data1 = self.blob_source.get_blob_reader(pieces[-1]['source'], pieces[-1]['offset'], blob_read_size).read()
        data2 = self.blob_source.get_blob_reader(blob, blob_start, blob_read_size).read()
        if data1 != data2:
            return
        # We can extend!
        pieces[-2]['size'] += pieces[-1]['size']
        del pieces[-1]  

    def __polish_recipe_repeats(self):
        assert self.recipe
        pieces = self.recipe['pieces']
        if len(pieces) == 0:
            return
        new_pieces = [pieces.pop(0)]
        assert new_pieces[-1]['repeat'] == 1
        for piece in pieces:
            assert piece['repeat'] == 1
            if new_pieces[-1]['source'] == piece['source'] and \
                    new_pieces[-1]['size'] == piece['size'] and \
                    new_pieces[-1]['offset'] == piece['offset'] and \
                    new_pieces[-1]['original'] == piece['original'] and \
                    new_pieces[-1]['original'] == False:
                new_pieces[-1]['repeat'] += 1
            else:
                new_pieces.append(piece)
        self.recipe['pieces'] = new_pieces            

    def get_recipe(self):
        assert self.closed
        if self.recipe == None:
            self.recipe = OrderedDict([("md5sum", self.md5summer.hexdigest()),
                                       ("size", self.tail_buffer.virtual_size()),
                                       ("method", "concat"),
                                       ("pieces", list(self.__seq2rec()))])
            # We now have a complete and useful recipe. But can it be improved?
            self.__polish_recipe_tail()
            self.__polish_recipe_repeats()
        return self.recipe

class BlockSequenceFinder:
    def __init__(self, blocksdb):
        self.blocksdb = blocksdb

        # The candidates are tuples on the form (blob, offset), where
        # offset is the end of the last matched block.
        self.candidates = set()
        self.feeded_blocks = 0

        self.firstblock = True
        self.block_size = blocksdb.get_block_size()

    def get_matches(self):
        length = self.block_size * self.feeded_blocks
        for blob, end_pos in sorted(self.candidates):
            # By sorting, we get a predictable order which makes
            # testing easier. As a secondary effect, we also
            # concentrate the hits to fewer blobs (the ones with lower
            # blob-ids), which may have positive cache effects on
            # access.
            start_pos = end_pos - length
            assert start_pos >= 0
            yield blob, start_pos, length

    def can_add(self, block_md5):
        return self.firstblock or bool(self.__filter_and_extend_candidates(block_md5))

    def __filter_and_extend_candidates(self, block_md5):
        """ Returns the candidates that can be extended with the given block."""
        surviving_candidates = set()
        for block in self.candidates.intersection(set(self.blocksdb.get_block_locations(block_md5))):
            blob, offset = block
            surviving_candidates.add((blob, offset + self.block_size))
        return surviving_candidates

    def add_block(self, block_md5):
        self.feeded_blocks += 1
        if self.firstblock:
            self.firstblock = False
            for blob, offset in self.blocksdb.get_block_locations(block_md5):
                self.candidates.add((blob, offset + self.block_size))
        else:
            self.candidates = self.__filter_and_extend_candidates(block_md5)
        assert self.candidates, "No remaining candidates"
        #print "Candidates are", list(self.get_matches())

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
    size = 0
    for n in range(0,10000):
        b.feed_string(data)
        size += len(data)
        b.harvest()
    print size, time.time() - t0

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

