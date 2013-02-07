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

class blobs_blocks:
    def __init__(self, dbfile = ":memory:"):
        self.conn = None
        self.dbfile = dbfile
        self.__init_db()

    def __init_db(self):
        if self.conn:
            return
        try:
            self.conn = sqlite3.connect(self.dbfile, check_same_thread = False)
            self.conn.execute("CREATE TABLE IF NOT EXISTS blocks (blob char(32) NOT NULL, offset long NOT NULL, sha256 char(64) NOT NULL, row_md5 char(32))")
            self.conn.execute("CREATE TABLE IF NOT EXISTS rolling (value INT NOT NULL)") 
            self.conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS index_rolling ON rolling (value)")
            self.conn.execute("CREATE INDEX IF NOT EXISTS index_sha256 ON blocks (sha256)")
            self.conn.commit()
        except sqlite3.DatabaseError, e:
            raise repository.SoftCorruptionError(e)

    def get_blob_location(self, sha256):
        c = self.conn.cursor()
        c.execute("SELECT blob, offset, row_md5 FROM blocks WHERE sha256 = ?", [sha256])
        row = c.fetchone()
        blob, offset, row_md5 = row
        if row_md5 != md5sum("%s-%s-%s" % (blob, offset, sha256)):
            raise repository.SoftCorruptionError("Corrupted row in deduplication block table for (%s %s %s)" % (blob, offset, sha256))
        return blob, offset

    def get_all_rolling(self):
        c = self.conn.cursor()
        c.execute("SELECT value FROM rolling")
        rows = c.fetchall()
        values = [row[0] for row in rows]
        return values

    def has_block(self, sha256):
        c = self.conn.cursor()
        c.execute("SELECT 1 FROM blocks WHERE sha256 = ?", [sha256])
        rows = c.fetchall()
        if rows:
            return True
        return False

    def add_block(self, blob, offset, sha256):
        assert is_md5sum(blob)
        assert len(sha256) == 64, repr(sha256)
        md5_row = md5sum("%s-%s-%s" % (blob, offset, sha256))
        try:
            self.conn.execute("INSERT INTO blocks (blob, offset, sha256, row_md5) VALUES (?, ?, ?, ?)", (blob, offset, sha256, md5_row))
        except sqlite3.DatabaseError, e:
            raise repository.SoftCorruptionError("Exception while writing to the blocks cache: "+str(e))

    def add_rolling(self, rolling):
        assert 0 <= rolling <= 2**32 - 1
        self.conn.execute("INSERT OR IGNORE INTO rolling (value) VALUES (?)", [rolling])

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

