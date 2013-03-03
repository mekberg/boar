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
        self.dbfile = dbfile
        self.__init_db(block_size)

    def __init_db(self, block_size):
        assert type(block_size) == int and block_size > 0
        assert not self.conn
        try:
            self.conn = sqlite3.connect(self.dbfile, check_same_thread = False)
            pragmas = \
                "PRAGMA main.page_size = 4096;", \
                "PRAGMA main.cache_size=10000;", \
                "PRAGMA main.locking_mode=NORMAL;", \
                "PRAGMA main.synchronous=OFF;" # TODO: replace with WAL
                #"PRAGMA main.journal_mode=WAL;" # Requires sqlite 3.7.0
            for pragma in pragmas:
                self.conn.execute(pragma)
            self.conn.execute("CREATE TABLE IF NOT EXISTS blocks (blob char(32) NOT NULL, offset long NOT NULL, md5 char(32) NOT NULL, row_md5 char(32))")
            self.conn.execute("CREATE TABLE IF NOT EXISTS rolling (value INT NOT NULL)") 
            self.conn.execute("CREATE TABLE IF NOT EXISTS props (name TEXT PRIMARY KEY, value TEXT)")
            self.conn.execute("INSERT OR IGNORE INTO props VALUES ('block_size', ?)", [block_size])
            self.conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS index_rolling ON rolling (value)")
            self.conn.execute("CREATE INDEX IF NOT EXISTS index_md5 ON blocks (md5)")
            self.conn.commit()            
            assert self.get_block_size() == block_size

        except sqlite3.DatabaseError, e:
            raise repository.SoftCorruptionError(e)

    def get_sequence_finder(self):
        return BlockSequenceFinder(self)

    def get_block_size(self):
        c = self.conn.cursor()
        c.execute("SELECT value FROM props WHERE name = 'block_size'")
        value, = c.fetchone()
        return int(value)

    def get_block_locations(self, block_md5, limit = -1):
        c = self.conn.cursor()
        c.execute("SELECT blob, offset, row_md5 FROM blocks WHERE md5 = ? LIMIT ?", [block_md5, limit])
        rows = c.fetchall()
        for row in rows:
            blob, offset, row_md5 = row
            assert_block_row_integrity(blob, offset, block_md5, row_md5)
            yield blob, offset

    def get_all_rolling(self):
        c = self.conn.cursor()
        c.execute("SELECT value FROM rolling")
        rows = c.fetchall()
        values = [signed2unsigned(row[0]) for row in rows]
        return values

    def has_block(self, md5):
        sw = StopWatch(False)
        c = self.conn.cursor()
        c.execute("SELECT 1 FROM blocks WHERE md5 = ?", [md5])
        rows = c.fetchall()
        sw.mark("blocksdb.has_block()")
        if rows:
            return True
        return False

    def add_block(self, blob, offset, md5):
        assert is_md5sum(blob)
        assert len(md5) == 32, repr(md5)
        md5_row = block_row_checksum(blob, offset, md5)
        try:
            self.conn.execute("INSERT INTO blocks (blob, offset, md5, row_md5) VALUES (?, ?, ?, ?)", (blob, offset, md5, md5_row))
        except sqlite3.DatabaseError, e:
            raise repository.SoftCorruptionError("Exception while writing to the blocks cache: "+str(e))

    def add_rolling(self, rolling):        
        assert 0 <= rolling <= (2**64 - 1) # Must be within the SIGNED range - stupid sqlite
        rolling_signed = unsigned2signed(rolling)
        assert -2**63 <= rolling_signed <= 2**63 -1
        self.conn.execute("INSERT OR IGNORE INTO rolling (value) VALUES (?)", [str(rolling_signed)])
        assert rolling in self.get_all_rolling(), rolling


    def verify(self):
        assert False, "not implemented"
        
    def commit(self):
        if self.conn:
            self.conn.commit()

    def close(self):
        self.commit()
        if self.conn:
            self.conn.close()
            self.conn = None

