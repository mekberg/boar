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
from common import *

class blobs_sha256:
    def __init__(self, repo, datadir):
        self.repo = repo
        assert os.path.exists(datadir)
        assert os.path.isdir(datadir)
        self.datadir = datadir
        self.conn = None

    def __init_db(self):
        if self.conn:
            return
        try:
            self.conn = sqlite3.connect(os.path.join(self.datadir, "sha256cache"))
            c = self.conn.cursor()
            c.execute("CREATE TABLE IF NOT EXISTS checksums (md5 char(32) PRIMARY KEY, sha256 char(64) NOT NULL)")
        except Exception, e:
            warn("Exception while initializing blobs_sha256 derived database - harmless but things may be slow\n")
            warn("The reason was: "+ str(e))

    def __set_result(self, md5, sha256):
        self.__init_db()
        try:
            c = self.conn.cursor()
            c.execute("INSERT INTO checksums (md5, sha256) VALUES (?, ?)", (md5, sha256))
        except Exception, e:
            warn("Exception while writing to blobs_sha256 derived database - harmless but things may be slow\n")
            warn("The reason was: "+ str(e))


    def __get_result(self, md5):
        self.__init_db()
        try:
            c = self.conn.cursor()
            c.execute("SELECT sha256 FROM checksums WHERE md5 = ?", (md5,))
            rows = c.fetchall()
            if rows:
                assert len(rows) == 1
                return rows[0][0]
        except:
            warn("Exception while reading from blobs_sha256 derived database - harmless but things may be slow\n")
        return None

    def get_sha256(self, blob):
        result = self.__get_result(blob)
        if result:
            return result
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
        result = sha256.hexdigest()
        self.__set_result(blob, result)
        return result
        
    
