#!/usr/bin/env python
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
import hashlib
import os
import sqlite3
from weakref import proxy
from common import *
from boar_common import safe_delete_file
import atexit
import repository
import struct
import rollingcs

def unsigned2signed(u):
    s = struct.pack("Q", long(u))
    return struct.unpack("q", s)[0]

def signed2unsigned(d):
    s = struct.pack("q", long(d))
    return struct.unpack("Q", s)[0]

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

def block_row_checksum(blob, offset, block_md5):
    return md5sum("%s-%s-%s" % (blob, offset, block_md5))

def assert_block_row_integrity(blob, offset, block_md5, expected_row_checksum):
    if expected_row_checksum != block_row_checksum(blob, offset, block_md5):
        raise repository.SoftCorruptionError("Corrupted row in deduplication block table for (%s %s %s)" % (blob, offset, block_md5))

class BlockLocationsDB:
    def __init__(self, block_size, dbfile = ":memory:"):
        self.conn = None
        self.db = rollingcs.BlocksDB(dbfile)
        self.block_size = block_size

    def get_sequence_finder(self):
        return BlockSequenceFinder(self)

    def get_block_size(self):
        return self.block_size

    def get_block_locations(self, block_md5, limit = -1):
        for row in self.db.get_blocks(block_md5, limit):
            blob, offset, row_md5 = row
            #assert_block_row_integrity(blob, offset, block_md5, row_md5)
            yield blob, offset

    def get_all_rolling(self):
        return self.db.get_all_rolling()

    def has_block(self, md5):
        return self.db.has_block(md5)

    def add_block(self, blob, offset, md5):
        self.db.add_block(blob, offset, md5)

    def add_rolling(self, rolling):        
        self.db.add_rolling(rolling)

    def verify(self):
        assert False, "not implemented"

    def begin(self):
        self.db.begin()
    
    def commit(self):
        self.db.commit()

    def close(self):
        self.commit()
        if self.conn:
            self.conn.close()
            self.conn = None

