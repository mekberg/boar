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
            block_rolling = calc_rolling(block, self.window_size)
            self.blocks.append((self.position, block_rolling, block_sha256))
            self.position += self.window_size
            self.buffer = self.buffer[self.window_size:]

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

    def __init__(self, tail_size):
        #self.tail_size = tail_size
        self.buffer = ""
        self.offset = 0
        
    def append(self, s):
        self.buffer += s

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
        pass    

class RecipeFinder:
    def __init__(self, blocksdb, block_size, all_rolling, blob_source, original_piece_handler = OriginalPieceHandler()):
        self.blocksdb = blocksdb
        self.block_size = block_size
        self.rs = RollingChecksum(block_size)
        self.rs.add_needles(all_rolling)
        self.blob_source = blob_source
        self.original_piece_handler = original_piece_handler

        self.tail_buffer = TailBuffer(self.block_size*2)
        self.end_of_last_hit = 0
        self.original_run_since = None
        self.addresses = []
        self.md5summer = hashlib.md5()
        self.original_piece_count = 0
        self.closed = False

    def feed(self, s):
        assert len(s) <= self.block_size
        assert not self.closed
        self.rs.feed_string(s)
        self.md5summer.update(s)
        self.tail_buffer.append(s)
        for offset, rolling in self.rs:
            if offset < self.end_of_last_hit:
                # Ignore overlapping blocks
                continue
            sha = sha256(self.tail_buffer[offset : offset + self.block_size])
            if self.blocksdb.has_block(sha):
                self.__add_hit(offset, sha)

    def close(self):
        assert not self.closed
        self.closed = True
        self.__add_original(self.end_of_last_hit, len(self.tail_buffer))
        original_size = len(self.tail_buffer)
        recipe_size = 0
        for a in self. addresses:
            recipe_size += a.size
        assert original_size == recipe_size
        del self.rs

    def modify_piece(self, index, blob, offset):
        assert self.closed
        addresses = [a for a in self.addresses if a.piece_index == index]
        assert len(addresses) == 1
        p = addresses[0]
        p.blob = blob
        p.blob_offset = offset

    def get_recipe(self):
        assert self.closed
        pieces = []
        for address in self.addresses:
            assert address.size > 0
            pieces.append({"source": address.blob, "offset": address.blob_offset, "size":  address.size})

        result = {"method": "concat",
                  "md5sum": self.md5summer.hexdigest(),
                  "size": len(self.tail_buffer),
                  "pieces": pieces}

        return result

    def __add_original(self, start_offset, end_offset):
        assert 0 <= start_offset <= end_offset
        if start_offset == end_offset:
            return
        assert start_offset < end_offset
        self.original_piece_handler.init_piece(self.original_piece_count)
        self.original_piece_handler.add_piece_data(self.original_piece_count, self.tail_buffer[start_offset:end_offset])
        self.original_piece_handler.end_piece(self.original_piece_count)
        #print "Found original data at %s+%s" % ( start_offset, end_offset - start_offset)
        self.__add_address(Struct(match_start = start_offset, blob = None, piece_index = self.original_piece_count, blob_offset = start_offset, size = end_offset - start_offset))
        self.original_piece_count += 1

    def __add_hit(self, offset, sha):
        assert offset >= self.end_of_last_hit
        hit_size = self.block_size
        hit_bytes = self.tail_buffer[offset : offset + hit_size]

        blob, blob_offset = self.blocksdb.get_blob_location(sha)
        #print "Found block hit at %s+%s (pointing at %s %s)" % ( offset, hit_size, blob, blob_offset)
        # We have found a hit, but it might be possible to grow it.
        preceeding_original_data_size = offset - self.end_of_last_hit
        potential_growth_size = min(blob_offset, preceeding_original_data_size)
        potential_match = self.blob_source.get_blob_reader(blob, 
                                                           offset=blob_offset - potential_growth_size, 
                                                           size=potential_growth_size).read(potential_growth_size)
        match_length = len(common_tail(hit_bytes, potential_match))

        offset -= match_length
        blob_offset -= match_length
        hit_size += match_length
        del sha # No longer valid

        #if match_length: print "Block hit was expanded to %s+%s" % ( offset, hit_size)

        # There is original data from the end of the last true
        # hit, up to the start of this true hit.
        self.__add_original(self.end_of_last_hit, offset)
        self.__add_address(Struct(match_start = offset, blob = blob, piece_index = None, blob_offset = blob_offset, size = hit_size))
        
        self.end_of_last_hit = offset + hit_size

    def __add_address(self, new_address):
        if not self.addresses:
            #print "Adding (appended first)", new_address
            self.addresses.append(new_address)
        else:
            prev_address = self.addresses[-1]
            if prev_address.blob == new_address.blob and \
                    new_address.blob_offset == prev_address.blob_offset + prev_address.size:
                    #prev_address.match_start + prev_address.size == new_address.match_start:
                prev_address.size += new_address.size
                #print "Adding (joined)", new_address
            else:
                self.addresses.append(new_address)
                #print "Adding (appended)", new_address
                    
            
def print_recipe(recipe):
    print "Md5sum:", recipe["md5sum"]
    print "Size  :", recipe["size"]
    print "Method:", recipe['method']
    print "Pieces:", len(recipe['pieces'])
    pos = 0
    dedup_size = 0
    for p in recipe['pieces']:
        print "  Source blob  :", p['source'] if p['source'] else "SELF"
        print "  Source offset:", p['offset']
        print "  Size         :", p['size']
        print "  Position     : %s - %s" % (pos, pos + p['size'])
        print "  ---------------"
        pos += p['size']
        if p['source'] == None: # Count the parts we couldn't find elsewhere
            dedup_size += p['size']
    try:
        print "Dedup removed %s%% of original size" % round((100.0 * (1.0 - float(dedup_size) / recipe["size"])), 1)
    except ZeroDivisionError:
        print "Zero size recipe"
        pass

def recepify(front, filename, local_blob_dir = None):
    WINDOW_SIZE = front.get_dedup_block_size()
    blob_source = UniformBlobGetter(front.repo, local_blob_dir)
    original_size = os.path.getsize(filename)
    if original_size == 0:
        # Zero length files don't deduplicate well...
        return None

    finder = RecipeFinder(front.repo.blocksdb, WINDOW_SIZE, front.get_all_rolling(), blob_source)
    f = safe_open(filename, "rb")
    for block in file_reader(f, blocksize = WINDOW_SIZE):
        finder.feed(block)
    finder.close()
    f.close()

    recipe = finder.get_recipe()

    return recipe


