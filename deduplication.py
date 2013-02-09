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
            

#########################




def grow_address_upwards(blob_source, bytearray, address, grow_bite, max_grow_size):
    blob_size = blob_source.get_blob_size(address['blob'])
    upper_block_start = address['blob_offset'] + address['size']
    upper_block_end = min(blob_size, upper_block_start+grow_bite)
    upper_block_size = upper_block_end - upper_block_start
    upper_block = blob_source.get_blob(address['blob'], upper_block_start, upper_block_size).read()
    growth = 0
    while address['match_start'] + address['size'] < len(bytearray) and growth < upper_block_size and growth < max_grow_size:
        if bytearray[address['match_start'] + address['size']] != upper_block[growth]:
            break
        growth += 1
        address['size'] += 1
    return growth

def grow_address_downwards(blob_source, bytearray, address, grow_bite, max_grow_size):
    blob_size = blob_source.get_blob_size(address['blob'])
    lower_block_start = max(0, address['blob_offset'] - grow_bite)
    lower_block_end = address['blob_offset']
    lower_block_size = lower_block_end - lower_block_start
    lower_block = blob_source.get_blob(address['blob'], lower_block_start, lower_block_size).read()
    growth = 0
    while address['match_start'] > 0 and growth < lower_block_size and growth < max_grow_size:
        if bytearray[address['match_start'] - 1] != lower_block[-(growth+1)]:
            break
        growth += 1
        address['blob_offset'] -= 1
        address['match_start'] -= 1
        address['size'] += 1
    return growth

class UniformBlobGetter:
    def __init__(self, front, local_blob_dir = None):
        self.front = front
        self.local_blob_dir = local_blob_dir

    def get_blob_size(self, blob_name):
        assert is_md5sum(blob_name)
        if self.local_blob_dir:
            local_path = os.path.join(self.local_blob_dir, blob_name)
            if os.path.exists(local_path):
                return long(os.path.getsize(local_path))
        return self.front.get_blob_size(blob_name)

    def get_blob(self, blob_name, offset, size):
        assert is_md5sum(blob_name)
        if self.local_blob_dir:
            local_path = os.path.join(self.local_blob_dir, blob_name)
            if os.path.exists(local_path):
                fo = safe_open(local_path, "rb")
                fo.seek(offset)                
                return FileDataSource(fo, size)
        return self.front.get_blob(blob_name, offset, size)

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

class RecipeFinder:
    def __init__(self, front, block_size, all_rolling, blob_source, original_piece_directory = None):
        self.front = front
        self.block_size = block_size
        self.rs = RollingChecksum(block_size)
        self.rs.add_needles(all_rolling)
        self.blob_source = blob_source
        self.original_piece_directory = original_piece_directory
        assert self.original_piece_directory == None or os.path.isdir(self.original_piece_directory)

        self.tail_buffer = TailBuffer(self.block_size*2)
        self.end_of_last_hit = 0
        self.original_run_since = None
        self.addresses = []
        self.md5summer = hashlib.md5()

    def feed(self, s):
        assert len(s) <= self.block_size
        self.md5summer.update(s)
        self.rs.feed_string(s)
        self.tail_buffer.append(s)
        for offset, rolling in self.rs:
            if offset < self.end_of_last_hit:
                # Ignore overlapping blocks
                continue
            sha = sha256(self.tail_buffer[offset : offset + self.block_size])
            if self.front.has_block(sha):
                self.__add_hit(offset, sha)

    def close(self):
        self.__add_original(self.end_of_last_hit, len(self.tail_buffer))
        original_size = len(self.tail_buffer)
        recipe_size = 0
        for a in self. addresses:
            recipe_size += a.size
        assert original_size == recipe_size:
        del self.rs

    def get_recipe(self):
        pieces = []
        for address in self.addresses:
            assert address.size > 0
            pieces.append({"source": address.blob, "offset": address.blob_offset, "size":  address.size})

        return {"method": "concat",
                "md5sum": self.md5summer.hexdigest(),
                "size": len(self.tail_buffer),
                "pieces": pieces}


    def __add_original(self, start_offset, end_offset):
        assert 0 <= start_offset <= end_offset
        if start_offset == end_offset:
            return
        assert start_offset < end_offset
        if self.original_piece_directory:
            md5 = md5sum(self.tail_buffer[start_offset:end_offset])
            with StrictFileWriter(s.path.join(self.original_piece_directory, "piece-" + md5), md5, end_offset - start_offset) as f:
                f.write(self.tail_buffer[start_offset:end_offset])
        #print "Found original data at %s+%s" % ( start_offset, end_offset - start_offset)
        self.__add_address(Struct(match_start = start_offset, blob = None, blob_offset = start_offset, size = end_offset - start_offset))

    def __add_hit(self, offset, sha):
        assert offset >= self.end_of_last_hit
        hit_size = self.block_size
        hit_bytes = self.tail_buffer[offset : offset + hit_size]

        blob, blob_offset = self.front.get_dedup_block_location(sha)
        #print "Found block hit at %s+%s (pointing at %s %s)" % ( offset, hit_size, blob, blob_offset)
        # We have found a hit, but it might be possible to grow it.
        preceeding_original_data_size = offset - self.end_of_last_hit
        potential_growth_size = min(blob_offset, preceeding_original_data_size)
        potential_match = self.blob_source.get_blob(blob, offset=blob_offset - potential_growth_size, size=potential_growth_size).read()
        match_length = len(common_tail(hit_bytes, potential_match))

        offset -= match_length
        blob_offset -= match_length
        hit_size += match_length
        del sha # No longer valid

        if match_length:
            #print "Block hit was expanded to %s+%s" % ( offset, hit_size)
            pass
        # There is original data from the end of the last true
        # hit, up to the start of this true hit.
        self.__add_original(self.end_of_last_hit, offset)
        self.__add_address(Struct(match_start = offset, blob = blob, blob_offset = blob_offset, size = hit_size))
        
        #raw_addresses.append(address)
        #hits.append(offset)
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
                    
            
"""        
# Join consecutive addresses referring to the same blob
for address in raw_addresses:
    if address['blob'] == polished_addresses[-1]['blob'] and \
            address['blob_offset'] == polished_addresses[-1]['blob_offset'] + polished_addresses[-1]['size']:
        polished_addresses[-1]['size'] += address['size']
    else:
        polished_addresses.append(address)
"""     
    
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
    print "Dedup removed %s%% of original size" % round((100.0 * (1.0 - float(dedup_size) / recipe["size"])), 1)

def recepify(front, filename, local_blob_dir = None):
    WINDOW_SIZE = front.get_dedup_block_size()
    all_rolling = set(front.get_all_rolling())

    rs = RollingChecksum(WINDOW_SIZE)
    
    blob_source = UniformBlobGetter(front, local_blob_dir)
    raw_addresses = []
    original_size = os.path.getsize(filename)
    if original_size == 0:
        # Zero length files don't deduplicate well...
        return None
    f = safe_open(filename, "rb")
    bytearray = FileAsString(f)
    assert len(bytearray) == original_size

    rs.add_needles(all_rolling)

    data = f.read()

    #front, block_size, all_rolling, blob_source, original_piece_directory
    finder = RecipeFinder(front, WINDOW_SIZE, all_rolling, blob_source)
    for block in file_reader(f, blocksize = WINDOW_SIZE):
        finder.feed(block)

    rs.feed_string(data)
    hits = []
    last_true_hit = -WINDOW_SIZE
    for offset, rolling in rs:
        if offset < last_true_hit + WINDOW_SIZE:
            # Ignore overlapping blocks
            continue
        sha = sha256(bytearray[offset:offset+WINDOW_SIZE])
        if front.has_block(sha):
            blob, blob_offset = front.get_dedup_block_location(sha)
            address = {'match_start': offset, 'blob': blob, 'blob_offset': blob_offset, 'size': WINDOW_SIZE}
            raw_addresses.append(address)
            hits.append(offset)
            last_true_hit = offset
        else:
            pass
    del rs
    # No longer necessary
    # hits = remove_overlapping_blocks(hits, WINDOW_SIZE)

    raw_addresses = [t for t in raw_addresses if t['match_start'] in hits]

    if not raw_addresses:
        return None # No deduplication is possible

    polished_addresses = []
    polished_addresses.append(raw_addresses.pop(0))

    # Join consecutive addresses referring to the same blob
    for address in raw_addresses:
        if address['blob'] == polished_addresses[-1]['blob'] and \
                address['blob_offset'] == polished_addresses[-1]['blob_offset'] + polished_addresses[-1]['size']:
            polished_addresses[-1]['size'] += address['size']
        else:
            polished_addresses.append(address)
    del raw_addresses

    # Grow every hit up to one block if possible
    for n, address in enumerate(polished_addresses):
        predecessor = polished_addresses[n-1] if n >= 1 else None
        try: successor = polished_addresses[n+1]
        except IndexError: successor = None

        lower_gap = 0
        if predecessor:
            lower_gap = address['match_start'] - (predecessor['match_start'] + predecessor['size'])
        upper_gap = original_size - (address['match_start'] + address['size'])
        if successor:
            upper_gap = successor['match_start'] - (address['match_start'] + address['size'])

        grow_address_upwards(blob_source, bytearray, address, grow_bite = WINDOW_SIZE, max_grow_size = upper_gap)
        grow_address_downwards(blob_source, bytearray, address, grow_bite = WINDOW_SIZE, max_grow_size = lower_gap)

    pieces = []
    expected_md5 = md5sum_file(f)

    pos = 0    
    result_md5 = hashlib.md5()

    # Construct a recipe instance from the polished addresses
    for address in polished_addresses:
        assert address['size'] > 0
        if address['match_start'] != pos:
            result_md5.update(bytearray[pos:address['match_start']])
            pieces.append({"source": None, "offset": pos, "size":  address['match_start'] - pos})
            pos = address['match_start']
        pieces.append({"source": address['blob'], "offset": address['blob_offset'], "size":  address['size']})
        pos += address['size']
        block = blob_source.get_blob(address['blob'], address['blob_offset'], address['size']).read()
        result_md5.update(block)
    if pos != len(bytearray):
        pieces.append({"source": None, "offset": pos, "size":  len(bytearray) - pos})
        result_md5.update(bytearray[pos:])
    del polished_addresses

    recipe = {"method": "concat",
              "md5sum": expected_md5,
              "size": len(bytearray),
              "pieces": pieces}

    assert expected_md5 == result_md5.hexdigest()
    if len(pieces) == 1 and pieces[0]["source"] == None:
        return None # No deduplication possible
    assert len(recipe['pieces']) > 0

    finder.close()
    #print "Finder result:"
    #for address in finder.addresses:
    #    print address
    print "Official recipe:"
    print_recipe(recipe)
    print
    print "New recipe:"
    print_recipe(finder.get_recipe())
    
    recipe_sum = sum([piece['size'] for piece in recipe['pieces']])
    if recipe_sum != original_size:
        print "WARNING: old recepify() got the wrong size!"
    return finder.get_recipe()
    #return recipe


