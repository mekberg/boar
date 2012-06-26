# -*- coding: utf-8 -*-

# Copyright 2012 Mats Ekberg
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
import sys, os
import sqlite3
import zlib
import tempfile
import getpass
import math

from boar_exceptions import *
import front
from common import *
from boar_common import *
from blobrepo.sessions import bloblist_fingerprint

class AnonymousRepository(Exception):
    """This exception indicates that the given repository can not be
    uniquely identified, and therefore cacheing can not be used. This
    is likely due to a write-protected legacy repository. """
    pass

class DummyCache:
    def __init__(self, front):
        self.front = front

    def get_bloblist(self, revision, skip_verification = False):
        return self.front.get_session_bloblist(revision)

def assert_valid_bloblist(front, revision, bloblist):
    actual_fingerprint = bloblist_fingerprint(bloblist)
    expected_fingerprint = front.get_session_fingerprint(revision)
    assert is_md5sum(expected_fingerprint)
    assert actual_fingerprint == expected_fingerprint

class BlobListCache:
    def __init__(self, front, cachedir):
        identifier = front.get_repo_identifier()
        if not identifier:
            raise AnonymousRepository()
        self.front = front
        assert os.path.exists(cachedir) and os.path.isdir(cachedir)
        self.conn = sqlite3.connect(os.path.join(cachedir, "boarcache-v3-%s-%s.db" % (identifier, getpass.getuser())), check_same_thread = False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("CREATE TABLE IF NOT EXISTS blcache (filename, md5sum, mtime INTEGER, ctime INTEGER, size INTEGER)")
        self.conn.execute("CREATE TABLE IF NOT EXISTS revisions (revision INTEGER, blobinfos BLOB, CONSTRAINT nodupes UNIQUE (revision))")
        self.conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS blcache_index ON blcache (filename, md5sum, mtime, ctime, size)")
        self.conn.commit()

    def __store_bloblist(self, revision, bloblist):
        assert_valid_bloblist(self.front, revision, bloblist)
        conn = self.conn
        birows = []
        for bi in bloblist: 
            bparts = bi['filename'], bi['md5sum'], bi['mtime'], bi['ctime'], bi['size']
            conn.execute("INSERT OR IGNORE INTO blcache (filename, md5sum, mtime, ctime, size) VALUES (?, ?, ?, ?, ?)", 
                         bparts)
            cursor = conn.execute('SELECT rowid from blcache WHERE filename=? AND md5sum=? AND mtime=? AND ctime=? AND size=?', 
                      bparts)
            rowid = cursor.fetchone()[0]
            birows.append(rowid) 
        bf = BitField()
        bf.set_multiple_bits(birows)
        conn.execute("INSERT INTO revisions (revision, blobinfos) VALUES (?, ?)", 
                     [revision, sqlite3.Binary(bf.serialize())])


    def get_bloblist(self, revision, skip_verification = False):
        conn = self.conn
        conn.execute("BEGIN")
        cursor = conn.execute('SELECT revisions.blobinfos FROM revisions WHERE revision = ?', [revision])
        row = cursor.fetchone()
        if row:
            bf = BitField.deserialize(row[0])
            rows = ",".join(map(str,bf.get_ones_indices()))
            bloblist = list(conn.execute('SELECT blcache.* from blcache WHERE rowid IN (%s) ORDER BY filename' % rows))
        else:
            bloblist = self.front.get_session_bloblist(revision)
            self.__store_bloblist(revision, bloblist)
        conn.commit()
        if not skip_verification:
            assert_valid_bloblist(self.front, revision, bloblist)
        return bloblist

__caches = {}

def get_cache(front):
    global __caches
    if front not in __caches:
        try:
            cachedir = tempfile.gettempdir()
            __caches[front] = BlobListCache(front, cachedir)
        except AnonymousRepository:
            __caches[front] = DummyCache(front)
    return __caches[front]


class BitField:
    def __init__(self, value=0):
        self.value = value

    def __getitem__(self, index):
        return (self.value >> index) & 1 

    def __setitem__(self, index, value):
        value = (value & 1) << index
        mask = 1 << index
        self.value = (self.value & ~mask) | value

    def set_multiple_bits(self, lst):
        bitfield = 0
        for n in lst:
            bitfield |= (1 << n)
        self.value |= bitfield

    def get_ones_indices(self):
        bitstr = bin(self.value)[2:]
        result = [len(bitstr)-x[0]-1 for x in enumerate(bitstr) if x[1] == "1"]
        result.reverse()
        return result

    def serialize(self):
        return zlib.compress(bin(self.value))

    @staticmethod
    def deserialize(s):
        return BitField(int(zlib.decompress(s), 2))


def self_test1():
    bf1 = BitField()
    bf1.set_multiple_bits([0, 50, 1000])
    assert bf1.get_ones_indices() == [0, 50, 1000]
    bf2 = BitField.deserialize(bf1.serialize())
    assert bf2.get_ones_indices() == [0, 50, 1000]

def self_test2():
    bf1 = BitField()
    bf2 = BitField.deserialize(bf1.serialize())
    assert bf2.get_ones_indices() == []

def self_test3():
    bf1 = BitField()
    bf1[17] = 1
    bf1[170] = 1
    bf1[170] = 0
    bf2 = BitField.deserialize(bf1.serialize())
    assert bf2.get_ones_indices() == [17]
    
self_test1()
self_test2()
self_test3()
