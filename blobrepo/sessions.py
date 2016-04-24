# -*- coding: utf-8 -*-

# Copyright 2010 Mats Ekberg
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

import os
import tempfile
import re
import sys
import copy

import repository
from boar_exceptions import *

import shutil
import hashlib
import types

from common import *
from boar_common import *

import deduplication

"""
The SessionWriter and SessionReader are together with Repository the
only classes that directly accesses the repository. 

A session consists of a set of blobs and a set of metadatas. The
metadatas are dictionaries. Some keywords are reserved by the
repository, and some are required to be set by the client. Any
keys/values not specified here are stored and provided as they are.

md5sum:   Set/overwritten by the session.
filename: Required by the session, set by the client.
change:   Required by the session when creating a derived session. Can 
          be one of the following: add, remove, replace

The sessioninfo object also is mostly filled by the client, but a few
keywords are reserved.

base_session: The revision id of the revision that this revision is
        based on. May be null in case of a non-incremental revision.


"""

class AddException(Exception):
    pass

def bloblist_to_dict(bloblist):
    d = {}
    for b in bloblist:
        d[b['filename']] = b
    return d

def bloblist_fingerprint(bloblist):
    """Returns a hexadecimal string that is unique for a set of
    files."""
    md5 = hashlib.md5()
    blobdict = bloblist_to_dict(bloblist)
    filenames = blobdict.keys()
    filenames.sort()
    sep = "!SEPARATOR!"
    for fn in filenames:
        md5.update(fn.encode("utf-8"))
        md5.update(sep)
        md5.update(blobdict[fn]['md5sum'])
        md5.update(sep)
    return md5.hexdigest()

class _NaiveSessionWriter:
    """ This class takes care of the actual writing of data files to a
    snapshot directory. It checks its arguments for only the most
    basic errors. Specifically, it does not attempt to verify the
    existence of blobs, the validity of the fingerprint or the
    existence/validity of base snapshots. These things must be checked
    by the caller."""

    def __init__(self, session_name, base_session, path):
        assert session_name and isinstance(session_name, unicode)
        assert base_session == None or isinstance(base_session, int)
        assert os.path.exists(path) and os.path.isdir(path)
        assert (not os.listdir(path)) or os.listdir(path) == ["deleted"] # Allow for writing in snapshots currently being deleted
        self.session_name = session_name
        self.session_path = path
        self.datestr = None
        self.timestamp = None
        self.fingerprint = None
        self.base_session = base_session
        self.deleted_session_name = None
        self.deleted_fingerprint = None
        self.client_data = {"name": session_name}

        self.dead = False
        self.blobinfos = []
        self.seen_blobinfos = set()

    def cancel(self):
        self.dead = True

    def set_fingerprint(self, fingerprint):
        assert is_md5sum(fingerprint)
        self.fingerprint = fingerprint
    
    def add_blobinfo(self, blobinfo):
        assert type(blobinfo) == type({})
        #assert "size" in blobinfo
        assert "md5sum" in blobinfo and is_md5sum(blobinfo['md5sum'])
        #assert "mtime" in blobinfo and type(blobinfo['mtime']) == int
        #assert "ctime" in blobinfo and type(blobinfo['ctime']) == int
        assert "filename" in blobinfo
        assert blobinfo['filename'] not in self.seen_blobinfos
        self.seen_blobinfos.add(blobinfo['filename'])
        self.blobinfos.append(copy.copy(blobinfo))

    def add_action_remove(self, filename):
        assert filename not in self.seen_blobinfos
        self.seen_blobinfos.add(filename)
        self.blobinfos.append({"action": "remove",
                               "filename": filename})

    def delete(self, deleted_session_name, deleted_fingerprint):
        assert deleted_fingerprint == None or is_md5sum(deleted_fingerprint)
        assert deleted_session_name == None or type(deleted_session_name) == unicode
        assert (deleted_fingerprint == None) == (deleted_session_name == None)
        self.deleted_session_name = deleted_session_name
        self.deleted_fingerprint = deleted_fingerprint

    #def set_base_session(self, base_session):
    #    assert type(base_session) == int
    #    self.base_session = base_session

    def set_client_data(self, client_data):
        assert type(client_data) == type({})
        if "name" not in client_data:
            client_data['name'] = self.session_name
        self.client_data = copy.copy(client_data)

    def commit(self):
        assert not self.dead
        assert self.fingerprint
        assert self.client_data
        if self.deleted_session_name or self.deleted_fingerprint:
            assert self.deleted_session_name and self.deleted_fingerprint
            assert self.client_data['name'] == "__deleted"
            assert len(self.blobinfos) == 0
            assert self.base_session == None
        self.dead = True
        sessioninfo = {}
        sessioninfo['base_session'] = self.base_session
        sessioninfo['fingerprint'] = self.fingerprint
        sessioninfo['client_data'] = self.client_data
        if self.deleted_session_name:
            sessioninfo['deleted_name'] = self.deleted_session_name
        if self.deleted_fingerprint:            
            sessioninfo['deleted_fingerprint'] = self.deleted_fingerprint
        bloblist_filename = os.path.join(self.session_path, "bloblist.json")
        write_json(bloblist_filename, self.blobinfos)

        session_filename = os.path.join(self.session_path, "session.json")
        write_json(session_filename, sessioninfo)

        md5_filename = os.path.join(self.session_path, "session.md5")
        with open(md5_filename, "wb") as f:
            f.write(md5sum_file(bloblist_filename) + " *bloblist.json\n")
            f.write(md5sum_file(session_filename) + " *session.json\n")
        
        fingerprint_marker = os.path.join(self.session_path, self.fingerprint + ".fingerprint")
        with open(fingerprint_marker, "wb") as f:
            pass


class PieceHandler(deduplication.OriginalPieceHandler):
    """ A PieceHandler handles all the original data for a single
    uploaded blob. A continous length of original data is called a
    'piece'."""
    def __init__(self, session_dir, block_size, tmpdir, BlockifierClass):
        assert os.path.isdir(session_dir)
        assert block_size > 0
        self.block_size = block_size
        self.session_dir = session_dir
        self.blockifiers = {}
        self.blocks = None
        self.piece_start_offsets = {}
        self.current_index = None
        self.tmpdir = tmpdir
        self.BlockifierClass = BlockifierClass
        self.filename = os.path.join(self.session_dir, "amalgam")
        assert not os.path.exists(self.filename)
        self.fileobj = open(self.filename, "wb")
        self.md5summer = hashlib.md5()
        self.offset = 0

    @overrides(deduplication.OriginalPieceHandler)
    def init_piece(self, index):
        assert index >= 0
        assert self.current_index == None
        assert index not in self.blockifiers
        
        self.blockifiers[index] = self.BlockifierClass(self.block_size)
        self.piece_start_offsets[index] = self.offset
        self.current_index = index

    @overrides(deduplication.OriginalPieceHandler)
    def add_piece_data(self, index, data):
        assert self.current_index == index
        self.fileobj.write(data)
        self.md5summer.update(data)
        self.blockifiers[index].feed_string(data)
        self.offset += len(data)
        #print "Adding", len(data), "bytes"

    @overrides(deduplication.OriginalPieceHandler)
    def end_piece(self, index):
        sw = StopWatch(enabled=False)
        assert self.current_index == index
        self.current_index = None
        sw.mark("sessions.end_piece()")

    @overrides(deduplication.OriginalPieceHandler)
    def close(self):
        self.fileobj.close()
        self.fileobj = None
        self.final_md5 = self.md5summer.hexdigest()
        real_name = os.path.join(self.session_dir, self.final_md5)

        # The piece may already have been added during this commit. If
        # so, just ignore it.
        if os.path.exists(real_name):
            # Necessary for windows. Posix silently replaces an existing file.
            safe_delete_file(self.filename)
        else:
            os.rename(self.filename, real_name)

        self.blocks = []
        for index, blockifier in self.blockifiers.items():
            for offset, rolling, md5 in blockifier.harvest():
                self.blocks.append((self.final_md5, self.piece_start_offsets[index] + offset, rolling, md5))


    @overrides(deduplication.OriginalPieceHandler)
    def get_piece_address(self, index):
        assert self.fileobj == None
        return self.final_md5, self.piece_start_offsets[index]
        
class SessionWriter:
    def __init__(self, repo, session_name, base_session = None, session_id = None, force_base_snapshot = False):
        assert session_name and isinstance(session_name, unicode)
        assert base_session == None or isinstance(base_session, int)
        assert session_id == None or isinstance(session_id, int)
        assert isinstance(force_base_snapshot, bool)

        self.dead = False
        self.repo = repo
        self.tmpblocksdb = deduplication.TmpBlocksDB(self.repo.blocksdb)
        self.session_name = session_name
        self.max_blob_size = None
        self.base_session = base_session
        self.force_base_snapshot = force_base_snapshot
        self.metadatas = {}
        self.found_uncommitted_blocks = []
        self.blob_deduplicator = {}

        all_rolling = self.repo.blocksdb.get_all_rolling()
        self.rolling_set = deduplication.CreateIntegerSet(all_rolling)

        self.session_mutex = FileMutex(os.path.join(self.repo.repopath, repository.TMP_DIR), self.session_name)
        self.session_mutex.lock()
        assert os.path.exists(self.repo.repopath)
        currentmask = os.umask(0o777)
        os.umask(currentmask)
        self.session_path = tempfile.mkdtemp( \
            prefix = "tmp_", 
            dir = os.path.join(self.repo.repopath, repository.TMP_DIR))
        os.chmod(self.session_path, currentmask ^ 0o777)
        if self.force_base_snapshot:
            self.writer = _NaiveSessionWriter(session_name, None, self.session_path)
        else:
            self.writer = _NaiveSessionWriter(session_name, base_session, self.session_path)
        # The latest_snapshot is used to detect any unexpected
        # concurrent changes in the repo when it is time to commit.
        self.latest_snapshot = repo.find_last_revision(session_name)

        self.base_session_info = {}
        self.base_bloblist_dict = {} # All blobinfos in the base snapshot, as a dict
        if self.base_session != None:
            self.base_session_info = self.repo.get_session(self.base_session).get_properties()['client_data']
            self.base_bloblist_dict = bloblist_to_dict(\
                self.repo.get_session(self.base_session).get_all_blob_infos())
        self.resulting_blobdict = self.base_bloblist_dict # POTENTIAL BUG - should be copy?

        self.forced_session_id = None
        if session_id != None:
            self.forced_session_id = int(session_id)
            assert self.forced_session_id > 0

    def cancel(self):
        self.dead = True
        self.session_mutex.release()

    def deleted_snapshot(self, deleted_name, deleted_fingerprint):
        self.writer.delete(deleted_name, deleted_fingerprint)

    def erase_snapshots(self, snapshot_ids):
        for sid in snapshot_ids:
            assert type(sid) == int and sid > 0
        write_json(os.path.join(self.session_path, "delete.json"), snapshot_ids)

    def init_new_blob(self, blob_md5, blob_size):
        assert is_md5sum(blob_md5)
        # It is ok for a blob to already exist in the repo
        # here. Possibly some other session is uploading, or has
        # uploaded this blob, before we get here. But that is ok. 
        assert not self.dead  
        if self.repo.deduplication_enabled():
            assert deduplication.dedup_available, "Deduplication module not available"
            rollingchecksumclass = deduplication.RollingChecksum
            blockifierclass = deduplication.BlockChecksum
        else:
            rollingchecksumclass = deduplication.FakeRollingChecksum
            blockifierclass = deduplication.FakeBlockChecksum

        fname = os.path.join(self.session_path, blob_md5)
        blobsource = deduplication.UniformBlobGetter(self.repo, self.session_path)
        self.blob_deduplicator[blob_md5] = \
            deduplication.RecipeFinder(self.tmpblocksdb,
                                       repository.DEDUP_BLOCK_SIZE,
                                       self.rolling_set,
                                       blobsource,
                                       PieceHandler(self.session_path, repository.DEDUP_BLOCK_SIZE,
                                                    tmpdir = self.repo.get_tmpdir(),
                                                    BlockifierClass = blockifierclass),
                                       tmpdir = self.repo.get_tmpdir(),
                                       RollingChecksumClass = rollingchecksumclass)
        

    def add_blob_data(self, blob_md5, fragment):
        """ Adds the given fragment to the end of the new blob with the given checksum."""
        assert is_md5sum(blob_md5)
        assert not self.dead
        self.blob_deduplicator[blob_md5].feed(fragment)

    def blob_finished(self, blob_md5):
        sw = StopWatch(enabled=False, name="session.blob_finished")
        self.blob_deduplicator[blob_md5].close()
        for block in self.blob_deduplicator[blob_md5].original_piece_handler.blocks:
            # Let the recipe finder know about these blocks
            self.rolling_set.add(block[2])
            self.tmpblocksdb.add_tmp_block(md5 = block[3], blob = block[0], offset = block[1])
            self.found_uncommitted_blocks.append(block)
            
        sw.mark(1)
        recipe = self.blob_deduplicator[blob_md5].get_recipe()
        assert len(recipe['pieces']) > 0
        if len(recipe['pieces']) == 1 and recipe['pieces'][0]['source'] == blob_md5:
            recipe = None
        sw.mark(2)
        if recipe:
            recipe = self.blob_deduplicator[blob_md5].get_recipe()
            recipe_json = json.dumps(recipe, indent = 4)
            recipe_md5 = md5sum(recipe_json)
            recipe_path = os.path.join(self.session_path, blob_md5 + ".recipe")
            if not os.path.exists(recipe_path): # If it already exists, don't write it again
                with StrictFileWriter(recipe_path, recipe_md5, len(recipe_json)) as recipe_file:
                    recipe_file.write(recipe_json)
        sw.mark(3)
        del self.blob_deduplicator[blob_md5]
                
    def has_blob(self, csum):
        assert is_md5sum(csum)
        fname = os.path.join(self.session_path, csum)
        return os.path.exists(fname)

    def has_recipe(self, csum):
        assert is_md5sum(csum)
        fname = os.path.join(self.session_path, csum + ".recipe")
        return os.path.exists(fname)

    def add(self, metadata):
        assert not self.dead
        assert metadata.has_key('md5sum')
        assert metadata.has_key('filename')
        assert metadata['filename'].find("\\") == -1, \
            "Filenames must be in unix format"
        assert metadata['filename'].find("//") == -1, \
            "Filenames must be normalized. Was:" + metadata['filename']
        assert not metadata['filename'].startswith("/"), \
            "Filenames must not be absolute. Was:" + metadata['filename']
        assert not metadata['filename'].endswith("/"), \
            "Filenames must not end with a path separator. Was:" + metadata['filename']
        assert self.repo.has_blob(metadata['md5sum']) \
            or self.has_blob(metadata['md5sum']) \
            or self.has_recipe(metadata['md5sum']), \
            "Tried to add blob info, but no such blob exists: "+ metadata['md5sum']
        assert metadata['filename'] not in self.metadatas
        self.metadatas[metadata['filename']] = metadata
        self.resulting_blobdict[metadata['filename']] = metadata

    def remove(self, filename):
        assert not self.dead
        assert isinstance(filename, unicode)
        assert self.base_session
        assert self.base_bloblist_dict.has_key(filename)
        metadata = {'filename': filename,
                    'action': 'remove'}
        self.metadatas[filename] = metadata
        del self.resulting_blobdict[metadata['filename']]

    def commit(self, sessioninfo = {}, progress_callback = lambda x: None):
        assert not self.dead
        try:
            return self.__commit(sessioninfo, progress_callback=progress_callback)
        finally:
            self.session_mutex.release()

    def __commit(self, sessioninfo, progress_callback = lambda x: None):
        assert not self.dead
        assert self.session_path != None

        if "name" in sessioninfo:
            assert self.session_name == sessioninfo['name'], \
                "Committed session name '%s' did not match expected name '%s'" % \
                (sessioninfo['name'], self.session_name)
        self.writer.set_fingerprint(bloblist_fingerprint(self.resulting_blobdict.values()))
        self.writer.set_client_data(sessioninfo)

        snapshot_blobs = [filename for filename in os.listdir(self.session_path) if is_md5sum(filename)]

        for blob_name in snapshot_blobs:
            # Verify that all blobs still are there - as raw blobs or as recipes
            blob_path = os.path.join(self.session_path, blob_name)
            recipe_path = os.path.join(self.session_path, blob_name + ".recipe")
            assert os.path.exists(blob_path) or os.path.exists(recipe_path),\
                "a blob in the commit disappeared after deduplication"
            assert not(os.path.exists(blob_path) and os.path.exists(recipe_path)),\
                "a blob in the commit exists as both raw blob and recipe"

        if self.force_base_snapshot:
            bloblist = self.resulting_blobdict.values()
        else:
            bloblist = self.metadatas.values()

        for blobitem in bloblist:
            if "action" in blobitem:
                assert not self.force_base_snapshot
                self.writer.add_action_remove(blobitem['filename'])
            else:
                self.writer.add_blobinfo(blobitem)
        self.writer.commit()

        blocks_fname = os.path.join(self.session_path, "blocks.json")
        write_json(blocks_fname, self.found_uncommitted_blocks)

        # This is a fail-safe to reduce the risk of lockfile problems going undetected. 
        # It is not meant to be 100% safe. That responsibility lies with the lockfile.
        assert self.latest_snapshot == self.repo.find_last_revision(self.session_name), \
            "Session has been updated concurrently (Should not happen. Lockfile problems?) Commit aborted."
        session_id = self.repo.consolidate_snapshot(self.session_path, self.forced_session_id, progress_callback = progress_callback)
        return session_id
    
    def __del__(self):
        if self.session_mutex.is_locked():
            self.session_mutex.release()


class SessionReader:
    def __init__(self, repo, session_path):
        assert session_path, "Session path must be given"
        assert isinstance(session_path, unicode)
        if os.path.exists(os.path.join(session_path, "deleted")):
            # If a session is in the middle of being deleted, read all
            # data from the deletion folder instead
            session_path = os.path.join(session_path, "deleted")
        self.path = session_path
        self.dirname = os.path.basename(self.path)
        self.repo = repo
        assert os.path.exists(self.path), "No such session path:" + self.path
        self.raw_bloblist = None
        path = os.path.join(self.path, "session.json")
        try:
            self.properties = read_json(path)
        except ValueError:
            raise CorruptionError("Session data for snapshot %s is mangled" % self.dirname)
        self.fingerprint_file = os.path.join(self.path, self.get_fingerprint() + ".fingerprint")
        self.quick_verify()
        self.load_stats = None 

    def get_properties(self):
        """Returns a copy of the session properties."""
        return copy.copy(self.properties)

    def get_client_value(self, key):
        """ Returns the value of the client property with the name
        'key', or None if there are no such value """
        return self.properties['client_data'].get(key, None)

    def is_deleted(self):
        if "deleted_name" in self.properties:
            assert self.get_name() == "__deleted"
            return True
        elif self.get_name() == "__deleted":
            # Missing snapshots that are re-created as explicitly
            # deleted during an upgrade does not have deleted_name or
            # deleted_fingerprint in their properties.
            assert not "deleted_fingerprint" in self.properties
            return True
        return False

    def get_fingerprint(self):
        return self.properties['fingerprint']

    def get_name(self):
        return self.properties['client_data']['name']

    def get_base_id(self):
        base_session = None
        if "base_session" in self.properties and self.properties["base_session"] != None:
            base_session = int(self.properties["base_session"])
            assert base_session > 0
        return base_session

    def get_raw_bloblist(self):
        self.__load_raw_bloblist()
        return self.raw_bloblist

    def quick_verify(self):
        if not os.path.exists(self.path):
            raise CorruptionError("Session %s data not found" % self.dirname)
        files = os.listdir(self.path)
        fingerprint_files = [f for f in files if f.endswith(".fingerprint")]
        if len(fingerprint_files) > 1:
            raise CorruptionError("Session %s contains multiple fingerprint files" % self.dirname)
        if len(fingerprint_files) < 1:
            raise CorruptionError("Session %s is missing the fingerprint file" % self.dirname)
        if not (self.get_fingerprint() + ".fingerprint") in files:
            raise CorruptionError("Session %s has an invalid fingerprint file" % self.dirname)
        for md5, filename in read_md5sum(os.path.join(self.path, "session.md5")):
            if md5sum_file(os.path.join(self.path, filename)) != md5:
                raise CorruptionError("Internal file %s for snapshot %s does not match expected checksum" % (filename, self.dirname))

    def quick_quick_verify(self):
        if not os.path.exists(self.fingerprint_file):
            # Just a basic check so that we notice lost data quickly
            # (for instance, a boar server where some snapshots are
            # deleted by accident)
            raise CorruptionError("Session data not found: "+str(self.path))

    def __load_raw_bloblist(self):
        self.quick_verify()
        if self.raw_bloblist == None:
            path = os.path.join(self.path, "bloblist.json")
            try:
                self.raw_bloblist = read_json(path)
            except ValueError: # JSON decoding error
                raise CorruptionError("Bloblist for snapshot %s is mangled" % self.dirname)

    def get_all_blob_infos(self):
        # Diffucult to optimize this one. Caching the full blob list
        # is not necessarily faster. Caching the raw bloblists and
        # reconstructing the full bloblist as needed, seems to be the
        # way to go until we can cache the bloblist in binary form
        # somewhere.
        self.quick_quick_verify()
        session_obj = self
        all_session_objs = [self]
        while True:
            base_session_id = session_obj.properties.get("base_session", None)
            if base_session_id == None:
                break
            try:
                session_obj = self.repo.get_session(base_session_id)
            except MisuseError:
                # Missing session here means repo corruption
                raise CorruptionError("Required base snapshot %s is missing" % base_session_id)
            all_session_objs.insert(0, session_obj)
        self.load_stats = { "add_count": 0, "remove_count": 0, "total_count": 0 }
        bloblist = {}
        for session_obj in all_session_objs:
            rawbloblist = session_obj.get_raw_bloblist()
            for blobinfo in rawbloblist:
                if blobinfo.get("action", None) == "remove":
                    self.load_stats['remove_count'] += 1
                else:
                    self.load_stats['add_count'] += 1
            apply_delta(bloblist, rawbloblist)
        self.load_stats['total_count'] = len(bloblist)
        return bloblist.values()


