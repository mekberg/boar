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




def grow_address_upwards(blob_source, bytearray, address):
    grow_bite = 4096
    blob_size = blob_source.get_blob_size(address['blob'])
    upper_block_start = address['blob_offset'] + address['size']
    upper_block_end = min(blob_size, upper_block_start+grow_bite)
    upper_block_size = upper_block_end - upper_block_start
    upper_block = blob_source.get_blob(address['blob'], upper_block_start, upper_block_size).read()
    growth = 0
    while address['match_start'] + address['size'] < len(bytearray) and growth < upper_block_size:
        #print address
        if bytearray[address['match_start'] + address['size']] != upper_block[growth]:
            break
        growth += 1
        address['size'] += 1
    return growth

def grow_address_downwards(blob_source, bytearray, address):
    grow_bite = 4096
    blob_size = blob_source.get_blob_size(address['blob'])
    lower_block_start = max(0, address['blob_offset'] - grow_bite)
    lower_block_end = address['blob_offset']
    lower_block_size = lower_block_end - lower_block_start
    # print lower_block_start, lower_block_end, lower_block_size
    lower_block = blob_source.get_blob(address['blob'], lower_block_start, lower_block_size).read()
    growth = 0
    while address['match_start'] > 0 and growth < lower_block_size:
        #print address
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

def recepify(front, filename, local_blob_dir = None):
    WINDOW_SIZE = front.get_dedup_block_size()
    all_rolling = set(front.get_all_rolling())
    import mmap
    rs = RollingChecksum(WINDOW_SIZE)
    
    blob_source = UniformBlobGetter(front, local_blob_dir)
    raw_addresses = []
    if os.path.getsize(filename) == 0:
        # mmap has problems with zero size files, and anyway they
        # don't deduplicate well...
        return None
    f = safe_open(filename, "rb")
    bytearray = mmap.mmap(f.fileno(), 0, prot=mmap.PROT_READ)
    size = 0
    

    rs.add_needles(all_rolling)
    data = f.read()
    possible_hits = rs.feed_string(bytearray)
    hits = []
    for possible_hit in possible_hits:
        offset, rolling = possible_hit
        sha = sha256(bytearray[offset:offset+WINDOW_SIZE])
        if front.has_block(sha):
            blob, blob_offset = front.get_dedup_block_location(sha)
            address = {'match_start': offset, 'blob': blob, 'blob_offset': blob_offset, 'size': WINDOW_SIZE}
            raw_addresses.append(address)
            hits.append(offset)
        else:
            pass

    hits = remove_overlapping_blocks(hits, WINDOW_SIZE)
    raw_addresses = [t for t in raw_addresses if t['match_start'] in hits]

    if not raw_addresses:
        return None # No deduplication is possible

    polished_addresses = []
    polished_addresses.append(raw_addresses.pop(0))

    for address in raw_addresses:
        if address['blob'] == polished_addresses[-1]['blob'] and \
                address['blob_offset'] == polished_addresses[-1]['blob_offset'] + polished_addresses[-1]['size']:
            polished_addresses[-1]['size'] += address['size']
        else:
            polished_addresses.append(address)

    for address in polished_addresses:
        while grow_address_upwards(blob_source, bytearray, address): pass
        while grow_address_downwards(blob_source, bytearray, address): pass

    pieces = []
    expected_md5 = md5sum(bytearray)
    recipe = {"method": "concat",
              "md5sum": expected_md5,
              "size": len(bytearray),
              "pieces": pieces}

    pos = 0    
    result_md5 = hashlib.md5()

    for address in polished_addresses:
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
    assert expected_md5 == result_md5.hexdigest()
    if len(pieces) == 1 and pieces[0]["source"] == None:
        return None # No deduplication possible
    assert len(recipe['pieces']) > 0
    return recipe


#########################


def _extract_first_block_seq(offsets, block_size):
    """ Pulls out and removes the first sequence of 1 or more blocks
    from the offsets set. """
    assert type(offsets) == set
    cur = min(offsets)
    result = []
    while cur in offsets:
        offsets.remove(cur)
        result.append(cur)
        cur += block_size
    return result

assert _extract_first_block_seq(set([0, 5, 10, 15]), 10) == [0, 10]
assert _extract_first_block_seq(set([0, 5, 10, 15]), 5) == [0, 5, 10, 15]

def _find_all_block_seqs(offsets, block_size):
    offsets = set(offsets) # Create a copy 
    while offsets:
        yield _extract_first_block_seq(offsets, block_size)

def _find_longest_block_seq(offsets, block_size):
    longest = []
    for seq in _find_all_block_seqs(offsets, block_size):
        if len(seq) > len(longest):
            longest = seq
    return longest

assert _find_longest_block_seq([0, 1, 5, 6, 10, 11, 15, 16, 21], 5) == [1, 6, 11, 16, 21]
assert _find_longest_block_seq([], 5) == []

def _remove_overlapping(offsets, seq, block_size):
    low_limit = min(seq)
    high_limit = max(seq) + block_size - 1
    return set([n for n in offsets if n < low_limit or n > high_limit])

assert _remove_overlapping([0, 1, 2, 3, 4, 5], [1, 3], 2) == set([0, 5])

def remove_overlapping_blocks(offsets, block_size):
    result = []
    while offsets:
        longest_seq = _find_longest_block_seq(offsets, block_size)
        result += longest_seq
        offsets = _remove_overlapping(offsets, longest_seq, block_size)
    result.sort()
    return result

assert remove_overlapping_blocks([0,2,3,5,6,7,10,15], 5) == [0, 5, 10, 15]
assert remove_overlapping_blocks([0,2,3,5,6,7,10,15, 21, 22, 23], 5) == [0, 5, 10, 15, 21]

"""
import sys
rs = RollingChecksum(100)
for block in file_reader(sys.stdin):
    print len(block)
    rs.feed_string(block)
"""
