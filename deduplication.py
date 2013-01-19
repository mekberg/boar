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

    def harvest(self):
        result = self.blocks
        self.blocks = []
        return result
            

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


def RollingChecksum_self_test():
    rs = RollingChecksum(3)
    result = []
    for c in (0,1,2,3,0,1,2,3):
        rs.feed_byte(c)
        result.append(rs.value())
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


#########################




def grow_address_upwards(front, bytearray, address):
    grow_bite = 4096
    blob_size = front.get_blob_size(address['blob'])
    upper_block_start = address['blob_offset'] + address['size']
    upper_block_end = min(blob_size, upper_block_start+grow_bite)
    upper_block_size = upper_block_end - upper_block_start
    upper_block = front.get_blob(address['blob'], upper_block_start, upper_block_size).read()
    growth = 0
    while address['offset'] + address['size'] < len(bytearray) and growth < upper_block_size:
        #print address
        if bytearray[address['offset'] + address['size']] != upper_block[growth]:
            break
        growth += 1
        address['size'] += 1
    return growth

def grow_address_downwards(front, bytearray, address):
    grow_bite = 4096
    blob_size = front.get_blob_size(address['blob'])
    lower_block_start = max(0, address['blob_offset'] - grow_bite)
    lower_block_end = address['blob_offset']
    lower_block_size = lower_block_end - lower_block_start
    print lower_block_start, lower_block_end, lower_block_size
    lower_block = front.get_blob(address['blob'], lower_block_start, lower_block_size).read()
    growth = 0
    while address['offset'] > 0 and growth < lower_block_size:
        #print address
        if bytearray[address['offset'] - 1] != lower_block[-(growth+1)]:
            break
        growth += 1
        address['blob_offset'] -= 1
        address['offset'] -= 1
        address['size'] += 1
    return growth


def recepify(front, filename):
    WINDOW_SIZE = front.get_dedup_block_size()
    all_rolling = set(front.get_all_rolling())
    hits = []
    block_checksums = {}
    import mmap
    rs = RollingChecksum(WINDOW_SIZE)
    
    raw_addresses = []
    f = open(filename, "r")
    bytearray = mmap.mmap(f.fileno(), 0, prot=mmap.PROT_READ)
    size = 0

    for byte in bytearray:
        size += 1
        rs.feed_byte(ord(byte))
        rolling = rs.value()
        if rolling == None:
            continue
        if rolling in all_rolling:
            sha = rs.sha256()
            if front.has_block(rolling, sha):
                #address = [rs.offset()] + front.repo.blocksdb.get_blob_location(rolling, sha) + [WINDOW_SIZE]
                blob, blob_offset = front.get_dedup_block_location(rolling, sha)
                address = {'offset': rs.offset(), 'blob': blob, 'blob_offset': blob_offset, 'size': WINDOW_SIZE}
                #print "True hit at", address
                raw_addresses.append(address)
                hits.append(rs.offset())
                block_checksums[rs.offset()] = (rolling, sha)
            else:
                pass
                #print "False hit at", rs.offset()

    hits = remove_overlapping_blocks(hits, WINDOW_SIZE)
    raw_addresses = [t for t in raw_addresses if t['offset'] in hits]

    polished_addresses = []
    polished_addresses.append(raw_addresses.pop(0))
    # TODO: handle case with 0 raw_addresses

    for address in raw_addresses:
        if address['blob'] == polished_addresses[-1]['blob'] and \
                address['blob_offset'] == polished_addresses[-1]['blob_offset'] + polished_addresses[-1]['size']:
            polished_addresses[-1]['size'] += address['size']
        else:
            polished_addresses.append(address)

    for address in polished_addresses:
        while grow_address_upwards(front, bytearray, address): pass
        while grow_address_downwards(front, bytearray, address): pass

    pieces = []
    expected_md5 = md5sum(bytearray)
    recipe = {"method": "concat",
              "md5sum": expected_md5,
              "size": len(bytearray),
              "pieces": pieces}

    pos = 0
    
    result_md5 = hashlib.md5()
    #output = open("restored_file.bin", "w")
    for address in polished_addresses:
        if address['offset'] != pos:
            #print "%s-%s Original data (%s)" % (pos,  address['offset'], address['offset'] - pos)
            #output.write(bytearray[pos:address['offset']])
            result_md5.update(bytearray[pos:address['offset']])
            pieces.append({"source": None, "offset": address['offset'], "size":  address['offset'] - pos})
            pos = address['offset']
        #print address['offset'], address['blob'], address['blob_offset'], address['size']
        #print "%s-%s %s %s+%s" % (address['offset'], address['offset']+address['size'], address['blob'], address['blob_offset'], address['size'])
        pieces.append({"source": address['blob'], "offset": address['offset'], "size":  address['size']})
        pos += address['size']
        block = front.get_blob(address['blob'], address['blob_offset'], address['size']).read()
        #output.write(block)
        result_md5.update(block)
    if pos != len(bytearray):
        #print "%s-%s Original data (%s)" % (pos, len(bytearray), len(bytearray) - pos)
        pieces.append({"source": None, "offset": pos, "size":  len(bytearray) - pos})
        #output.write(bytearray[pos:])
        result_md5.update(bytearray[pos:])
    #print "*** End of recipe"
    assert expected_md5 == result_md5.hexdigest()
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

RollingChecksum_self_test()

"""
import sys
rs = RollingChecksum(100)
for block in file_reader(sys.stdin):
    print len(block)
    rs.feed_string(block)
"""
