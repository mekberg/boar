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

BLOBS_SHA256_DBFILE = "sha256cache"
BLOBS_BLOCKS_DBFILE = "blocksdb"

def verify_blobs_sha256(repo, datadir):
    try:
        sha256cache = blobs_sha256(repo, datadir)
    except repository.SoftCorruptionError, e:
        warn(str(e))
        return False
    if sha256cache.verify():
        return True
    warn("blobs_sha256 failed verification")
    return False

def reset_blobs_sha256(datadir):
    safe_delete_file(os.path.join(datadir, BLOBS_SHA256_DBFILE))

class blobs_sha256:
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
        atexit.register(self.sync)
        self.rate_limiter = RateLimiter(30.0)

    def __init_db(self):
        if self.conn:
            return
        try:
            self.conn = sqlite3.connect(os.path.join(self.datadir, BLOBS_SHA256_DBFILE), check_same_thread = False)
            self.conn.execute("CREATE TABLE IF NOT EXISTS checksums (md5 char(32) PRIMARY KEY, sha256 char(64) NOT NULL, row_md5 char(32))")
            self.conn.commit()
        except sqlite3.DatabaseError, e:
            raise repository.SoftCorruptionError(e)
            #raise repository.SoftCorruptionError("Exception while accessing the sha256 cache: "+str(e))

    def __set_result(self, md5, sha256):
        md5_row = md5sum(md5 + sha256)
        try:
            self.conn.execute("INSERT INTO checksums (md5, sha256, row_md5) VALUES (?, ?, ?)", (md5, sha256, md5_row))
        except sqlite3.DatabaseError, e:
            raise repository.SoftCorruptionError("Exception while writing to the sha256 cache: "+str(e))

    def __get_result(self, md5):
        try:
            c = self.conn.cursor()
            c.execute("SELECT md5, sha256, row_md5 FROM checksums WHERE md5 = ?", (md5,))
            rows = c.fetchall()
        except sqlite3.DatabaseError, e:
            raise repository.SoftCorruptionError("Exception while reading from the sha256 cache: "+str(e))
        if not rows:
            return None
        assert len(rows) == 1
        md5, sha256, row_md5 = rows[0]
        if row_md5 != md5sum(md5 + sha256):
            raise repository.SoftCorruptionError("Integrity check failed on a row in sha256 cache")
        return sha256

    def verify(self):
        try:
            c = self.conn.cursor()
            c.execute("SELECT md5, sha256 FROM checksums")
            rows = c.fetchall()
        except Exception, e:
            warn("Exception while verifying sha256 storage: "+str(e))
            self.__reset()
            return False
        for row in rows:
            md5, sha256 = row
            fresh_sha256 = self.__generate_sha256(md5)
            if fresh_sha256 != sha256:
                warn("Stored sha256 does not match calculated value")
                return False
            notice("Stored sha256 for %s seems correct" % md5)
        return True

    def __generate_sha256(self, blob):
        md5 = hashlib.md5()
        sha256 = hashlib.sha256()
        reader = self.repo.get_blob_reader(blob)
        assert reader
        while True:
            block = reader.read(2**16)
            if block == "":
                break
            sha256.update(block)
            md5.update(block)
        assert md5.hexdigest() == blob, "blob did not match expected checksum"
        return sha256.hexdigest()

    def get_sha256(self, blob):
        result = self.__get_result(blob)
        if self.rate_limiter.ready():
            self.sync()
        if result:
            return result
        result = self.__generate_sha256(blob)
        self.__set_result(blob, result)
        if self.rate_limiter.ready():
            self.sync()
        return result
        
    def sync(self):
        if self.conn:
            self.conn.commit()

    def close(self):
        self.sync()
        if self.conn:
            self.conn.close()
            self.conn = None


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
        atexit.register(self.sync)
        self.rate_limiter = RateLimiter(30.0)

    def __init_db(self):
        if self.conn:
            return
        try:
            self.conn = sqlite3.connect(os.path.join(self.datadir, BLOBS_BLOCKS_DBFILE), check_same_thread = False)
            self.conn.execute("CREATE TABLE IF NOT EXISTS blocks (blob char(32) NOT NULL, seq int NOT NULL, offset long NOT NULL, rolling char(32), sha256 char(64) NOT NULL, row_md5 char(32))")
            self.conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS blob_offset ON blocks (blob, offset)")
            self.conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS blob_seq ON blocks (blob, seq)")
            self.conn.execute("CREATE INDEX IF NOT EXISTS rolling ON blocks (rolling)")
            self.conn.commit()
        except sqlite3.DatabaseError, e:
            raise repository.SoftCorruptionError(e)

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
        
    def sync(self):
        if self.conn:
            self.conn.commit()

    def close(self):
        self.sync()
        if self.conn:
            self.conn.close()
            self.conn = None

