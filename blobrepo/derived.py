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

BLOBS_BLOCKS_DBFILE = "blocks.db"

class blobs_blocks:
    def __init__(self, repo, datadir):
        # Use a proxy to avoid circular reference to the repo,
        # allowing this object to be garbed at shutdown and triggering
        # the __del__ function.
        self.repo = proxy(repo)
        assert os.path.exists(datadir)
        assert os.path.isdir(datadir)
        self.datadir = datadir
        self.conn = None
        self.__init_db()

    def __init_db(self):
        if self.conn:
            return
        try:
            self.conn = sqlite3.connect(os.path.join(self.datadir, BLOBS_BLOCKS_DBFILE), check_same_thread = False)
            self.conn.execute("CREATE TABLE IF NOT EXISTS blocks (blob char(32) NOT NULL, seq int NOT NULL, offset long NOT NULL, rolling char(32), sha256 char(64) NOT NULL, row_md5 char(32))")
            self.conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS blob_offset ON blocks (blob, offset)")
            self.conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS blob_seq ON blocks (blob, seq)")
            self.conn.execute("CREATE INDEX IF NOT EXISTS rolling_sha256 ON blocks (rolling, sha256)")
            self.conn.commit()
        except sqlite3.DatabaseError, e:
            raise repository.SoftCorruptionError(e)

    def get_blob_location(self, rolling, sha):
        c = self.conn.cursor()
        c.execute("SELECT blob, offset FROM blocks WHERE rolling = ? AND sha256 = ?", [rolling, sha])
        row, = c.fetchall()
        return [row[0], row[1]]

    def get_all_rolling(self):
        c = self.conn.cursor()
        c.execute("SELECT DISTINCT rolling FROM blocks")
        rows = c.fetchall()
        values = [int(row[0]) for row in rows]
        return values

    def has_block(self, rolling, sha256):
        c = self.conn.cursor()
        c.execute("SELECT 1 FROM blocks WHERE rolling = ? AND sha256 = ?", [rolling, sha256])
        rows = c.fetchall()
        if rows:
            return True
        return False

    def add_block(self, blob, seq, offset, rolling, sha256):
        assert is_md5sum(blob)
        assert len(sha256) == 64, repr(sha256)
        assert type(rolling) == int, repr(rolling)
        assert type(seq) == int, repr(seq)
        md5_row = md5sum("%s-%s-%s-%s" % (blob, offset, rolling, sha256))
        try:
            self.conn.execute("INSERT INTO blocks (blob, seq, offset, rolling, sha256, row_md5) VALUES (?, ?, ?, ?, ?, ?)", (blob, seq, offset, rolling, sha256, md5_row))
        except sqlite3.DatabaseError, e:
            raise repository.SoftCorruptionError("Exception while writing to the blocks cache: "+str(e))

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

