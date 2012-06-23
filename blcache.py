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
import tempfile
import getpass

from boar_exceptions import *
import front
from common import *
from boar_common import *

class AnonymousRepository(Exception):
    """This exception indicates that the given repository can not be
    uniquely identified, and therefore cacheing can not be used. This
    is likely due to a write-protected legacy repository. """
    pass

class DummyCache:
    def __init__(self, front):
        self.front = front

    def get_bloblist(self, revision):
        return self.front.get_session_bloblist(revision)

class BlobListCache:
    def __init__(self, front):
        identifier = front.get_repo_identifier()
        if not identifier:
            raise AnonymousRepository()
        self.front = front
        self.conn = sqlite3.connect(os.path.join(tempfile.gettempdir(), "boarcache-%s-%s.db" % (identifier, getpass.getuser())), check_same_thread = False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("CREATE TABLE IF NOT EXISTS blcache (filename, md5sum, mtime INTEGER, ctime INTEGER, size INTEGER)")
        self.conn.execute("CREATE TABLE IF NOT EXISTS blcache_revs (revision INTEGER, blcache_rowid INTEGER, CONSTRAINT nodupes UNIQUE (revision, blcache_rowid))")
        self.conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS blcache_index ON blcache (filename, md5sum, mtime, ctime, size)")
        self.conn.commit()
        #conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS blcache_revs_index ON blcache_revs (revision, blcache_rowid)")

    def __store_bloblist(self, revision, bloblist):
        conn = self.conn
        for bi in bloblist: 
            bparts = bi['filename'], bi['md5sum'], bi['mtime'], bi['ctime'], bi['size']
            conn.execute("INSERT OR IGNORE INTO blcache (filename, md5sum, mtime, ctime, size) VALUES (?, ?, ?, ?, ?)", 
                         bparts)
            cursor = conn.execute('SELECT rowid from blcache WHERE filename=? AND md5sum=? AND mtime=? AND ctime=? AND size=?', 
                      bparts)
            rowid = cursor.fetchone()[0]
            conn.execute("INSERT OR IGNORE INTO blcache_revs (revision, blcache_rowid) VALUES (?, ?)", 
                         [revision, rowid])


    def get_bloblist(self, revision):
        conn = self.conn
        conn.execute("BEGIN")
        bloblist = list(conn.execute('SELECT blcache.* from blcache, blcache_revs WHERE blcache_revs.blcache_rowid = blcache.rowid AND blcache_revs.revision = ?', [revision]))
        if not bloblist:
            bloblist = self.front.get_session_bloblist(revision)
            self.__store_bloblist(revision, bloblist)
        conn.commit()
        return bloblist

__caches = {}

def get_cache(front):
    global __caches
    if front not in __caches:
        try:
            __caches[front] = BlobListCache(front)
        except AnonymousRepository:
            __caches[front] = DummyCache(front)
    return __caches[front]

