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
        self.scan_in_progress = False

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

    def set_sha256(self, md5, sha256):
        assert is_md5sum(md5)
        assert is_sha256(sha256)
        md5_row = md5sum(md5 + sha256)
        try:
            self.conn.execute("INSERT OR IGNORE INTO checksums (md5, sha256, row_md5) VALUES (?, ?, ?)", (md5, sha256, md5_row))
        except sqlite3.DatabaseError, e:
            raise repository.SoftCorruptionError("Exception while writing to the sha256 cache: "+str(e))
            

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

    def scan_init(self):
        self.scan_in_progress = True

    def scan_blob_init(self, md5):
        assert self.scan_in_progress
        self.currently_scanned_blob = md5
        self.currently_scanned_blob_md5 = hashlib.md5()
        self.currently_scanned_blob_sha256 = hashlib.sha256()

    def scan_blob_fragment(self, md5, block):
        assert self.scan_in_progress
        assert md5 == self.currently_scanned_blob
        self.currently_scanned_blob_md5.update(block)
        self.currently_scanned_blob_sha256.update(block)

    def scan_blob_finish(self, md5):
        assert self.scan_in_progress
        assert md5 == self.currently_scanned_blob
        assert md5 == self.currently_scanned_blob_md5.hexdigest()
        sha256_generated = self.currently_scanned_blob_sha256.hexdigest()
        sha256_from_db = self.__get_result(md5)
        if sha256_from_db:
            if sha256_generated != sha256_from_db:
                raise repository.SoftCorruptionError("Cached sha256 does not match generated value")
        else:
            self.__set_result(md5, sha256_generated)
        self.currently_scanned_blob = None
        self.currently_scanned_blob_sha256 = None
        self.currently_scanned_blob_md5 = None
        

    def scan_blob_abort(self, md5):
        assert self.scan_in_progress
        assert md5 == self.currently_scanned_blob
        self.currently_scanned_blob = None
        self.currently_scanned_blob_md5 = None
        self.currently_scanned_blob_sha256 = None

    def scan_finish(self):
        assert self.scan_in_progress
        pass
