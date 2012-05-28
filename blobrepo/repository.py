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

"""
The Repository together with SessionWriter and SessionReader are the
only classes that directly accesses the repository.
"""

import os
import re
import shutil
import sessions
import sys
import tempfile

from common import *
from boar_common import *
from blobreader import create_blob_reader
from jsonrpc import FileDataSource
from boar_exceptions import *

LATEST_REPO_FORMAT = 3
VERSION_FILE = "version.txt"
RECOVERYTEXT_FILE = "recovery.txt"
QUEUE_DIR = "queue"
BLOB_DIR = "blobs"
SESSIONS_DIR = "sessions"
RECIPES_DIR = "recipes"
TMP_DIR = "tmp"
DERIVED_DIR = "derived"
DERIVED_SHA256_DIR = "derived/sha256"
DELETE_MARKER = "deleted.json"

REPO_DIRS_V0 = (QUEUE_DIR, BLOB_DIR, SESSIONS_DIR, TMP_DIR)
REPO_DIRS_V1 = (QUEUE_DIR, BLOB_DIR, SESSIONS_DIR, TMP_DIR,\
    DERIVED_DIR, DERIVED_SHA256_DIR)
REPO_DIRS_V2 = (QUEUE_DIR, BLOB_DIR, SESSIONS_DIR, TMP_DIR,\
    DERIVED_DIR)
REPO_DIRS_V3 = (QUEUE_DIR, BLOB_DIR, SESSIONS_DIR, TMP_DIR,\
    DERIVED_DIR)

recoverytext = """Repository format v%s

This is a versioned repository of files. It is designed to be easy to
recover in case the original software is unavailable.

This document describes the layout of the repository, so that a
programmer can construct a simple program that recovers the data. To
extract the data, only basic programming skills are necessary. The
extraction can also be performed manually for individual files.

Note that it is always easier and safer to use the original software,
if possible. At the time of this writing, the boar software can be
downloaded at http://code.google.com/p/boar/

== The non-vital files ==

The repository contains files that are not useful for extracting
data. These are the "tmp", "derived", and "queue" folders. They can be
ignored for this purpose.

== The blobs == 

All files are stored verbatim in the "blobs" directory, named after
their md5 checksum, and sorted in sub directories based on the start
of their names. For instance, if a file "testimage.jpg" has the
checksum bc7b0fb8c2e096693acacbd6cb070f16, it will be stored in
blobs/bc/bc7b0fb8c2e096693acacbd6cb070f16 since the checksum starts
with the letters "bc". The filename "testimage.jpg" is discarded. Such
an anonymized file is called a "blob" in this document. 

== The sessions== 

All data files are in the JSON file format. It is quite simple, but if
you need details, see RFC4627.

The information necessary to reconstruct a file tree is stored under
the "sessions" directory. Each session consists of a series of
snapshots of a specific file tree. All snapshots have a revision id
corresponding to the name of the directory under "sessions". Each
snapshot represents a file tree at a point in time.

The details of a snapshot will be given in the files "session.json"
and "bloblist.json" (the bloblist). The bloblist contains the mapping
between filenames and blobs. To restore a snapshot, iterate over the
bloblist and copy the blob with the corresponding id to a file
with the name specified in the bloblist.

However, to completely restore a file tree, you must consider the
"base_session" value in session.json. If there is such a value, the
snapshot with that revision id must be extracted before the current
snapshot is extracted on top of it. This may repeat recursively until
a snapshot is found that does not have the base_session value set. In
other words, extraction must begin from the bottom of this
"base_session" chain. 

Every snapshot with a "base_session" value describes the changes that
needs to be applied to transform the base snapshot into the current
snapshot. Therefore, there are also special entries in the bloblist
that indicate that files should be removed from the base
snapshot. These are the entries containing a keyword "action" with the
value "remove". If you simply want to extract as much data as
possible, these special entries can be ignored.
""" % LATEST_REPO_FORMAT

verify_assert()

def misuse_assert(test, errormsg = None):
    if not test:
        raise MisuseError(errormsg)

def integrity_assert(test, errormsg = None):
    if not test:
        raise CorruptionError(errormsg)

def create_repository(repopath):
    os.mkdir(repopath)
    create_file(os.path.join(repopath, VERSION_FILE), str(LATEST_REPO_FORMAT))
    for d in QUEUE_DIR, BLOB_DIR, SESSIONS_DIR, TMP_DIR, DERIVED_DIR:
        os.mkdir(os.path.join(repopath, d))
    create_file(os.path.join(repopath, "recovery.txt"), recoverytext)

def is_recipe_filename(filename):
    filename_parts = filename.split(".")
    return len(filename_parts) == 2 \
        and filename_parts[1] == "recipe" \
        and is_md5sum(filename_parts[0])

def looks_like_repo(repo_path):
    """Superficial check to see if the given path contains anything
    resembling a repo of any version."""
    assert LATEST_REPO_FORMAT == 3 # Look through this function when updating format
    for dirname in (QUEUE_DIR, BLOB_DIR, SESSIONS_DIR, TMP_DIR):
        dirpath = os.path.join(repo_path, dirname)
        if not (os.path.exists(dirpath) and os.path.isdir(dirpath)):
            return False
    return True

def has_pending_operations(repo_path):
    dirpath = os.path.join(repo_path, QUEUE_DIR)
    return len(os.listdir(dirpath)) != 0

class Repo:
    def __init__(self, repopath):
        # The path must be absolute to avoid problems with clients
        # that changes the cwd. For instance, fuse.
        assert isinstance(repopath, unicode)
        assert(os.path.isabs(repopath)), "The repo path must be absolute. "\
            +"Was: " + repopath
        if not looks_like_repo(repopath):
            raise UserError("The path %s does not exist or does not contain a valid repository" % repopath)
        self.repopath = repopath
        if self.__get_repo_version() > LATEST_REPO_FORMAT:
            raise UserError("Repo is from a future boar version. Upgrade your boar.")
        self.session_readers = {}
        self.scanners = ()
        self.repo_mutex = FileMutex(os.path.join(repopath, TMP_DIR), "__REPOLOCK__")
        misuse_assert(os.path.exists(self.repopath), "No such directory: %s" % (self.repopath))

        self.readonly = False
        if not isWritable(os.path.join(repopath, TMP_DIR)):
            if self.get_queued_session_id() != None:
                raise UserError("Repo is write protected with pending changes. Cannot continue.")
            if self.__get_repo_version() not in (0, 1, 2, 3):
                # Intentional explicit counting so that we'll remember to check compatability with future versions
                raise UserError("Repo is write protected and from an unsupported older version of boar. Cannot continue.")
            notice("Repo is write protected - only read operations can be performed")
            self.readonly = True

        if not self.readonly:
            self.repo_mutex.lock_with_timeout(60)
            try:
                self.__upgrade_repo()
                self.__quick_check()
                self.process_queue()
            finally:
                self.repo_mutex.release()

    def __enter__(self):
        self.repo_mutex.lock()
        assert self.repo_mutex.is_locked()
        return self

    def __exit__(self, type, value, traceback):
        self.repo_mutex.release()

    def close(self):
        pass

    def __quick_check(self):
        """This method must be called after any repository upgrade
        procedure. It will assert that the repository is upgraded to
        the latest format and looks somewhat ok. It will raise an
        exception if an error is found."""
        repo_version = self.__get_repo_version()
        assert repo_version, "Repo format obsolete. Upgrade failed?"
        integrity_assert(repo_version == LATEST_REPO_FORMAT,
                         ("Repo version %s can not be handled by this version of boar" % repo_version))
        assert_msg = "Repository at %s is missing vital files. (Is it really a repository?)" % self.repopath
        assert LATEST_REPO_FORMAT == 3 # Check below must be updated when repo format changes
        for directory in REPO_DIRS_V3:
            integrity_assert(dir_exists(os.path.join(self.repopath, directory)), assert_msg)

    def allows_permanent_erase(self):
        return os.path.exists(os.path.join(self.repopath, "ENABLE_PERMANENT_ERASE"))

    def __upgrade_repo(self):
        assert not self.readonly, "Repo is read only, cannot upgrade"
        assert self.repo_mutex.is_locked()
        version = self.__get_repo_version()
        if version > LATEST_REPO_FORMAT:
            raise UserError("Repo version %s can not be handled by this version of boar" % version)
        if version == LATEST_REPO_FORMAT:
            return
        notice("Old repo format detected. Upgrading...")
        if self.__get_repo_version() == 0:
            self.__upgrade_repo_v0()
            assert self.__get_repo_version() == 1
        if self.__get_repo_version() == 1:
            self.__upgrade_repo_v1()
            assert self.__get_repo_version() == 2
        if self.__get_repo_version() == 2:
            self.__upgrade_repo_v2()
            assert self.__get_repo_version() == 3

        try:
            self.__quick_check()
        except:
            warn("Post-upgrade quickcheck of repository failed!")
            raise

    def __upgrade_repo_v0(self):
        """ This upgrade will upgrade a repository from before strict 
        version numbering (v0), to a v1 format repository. It does this by 
        performing the following actions:
        
        * Create directory "derived"
        * Create directory "derived/sha256"
        * Update "recovery.txt"
        * Create "version.txt" with value 1
        """
        assert not self.readonly, "Repo is read only, cannot upgrade"
        version = self.__get_repo_version()
        assert version == 0
        if not isWritable(self.repopath):
            raise UserError("Cannot upgrade repository - write protected")
        try:
            recipes_dir = os.path.join(self.repopath, RECIPES_DIR)
            if os.path.exists(recipes_dir):
                # recipes_dir is an experimental feature and should not contain
                # any data in a v0 repo (if it exists at all)
                try:
                    os.rmdir(recipes_dir)
                except:
                    raise UserError("Problem removing obsolete 'recipes' dir. Make sure it is empty and try again.")
            if not dir_exists(self.repopath + "/" + DERIVED_DIR):
                os.mkdir(self.repopath + "/" + DERIVED_DIR)
            if not dir_exists(os.path.join(self.repopath, DERIVED_SHA256_DIR)):
                os.mkdir(os.path.join(self.repopath, DERIVED_SHA256_DIR))
            replace_file(os.path.join(self.repopath, RECOVERYTEXT_FILE), recoverytext)
            version_file = os.path.join(self.repopath, VERSION_FILE)
            if os.path.exists(version_file):
                warn("Version marker should not exist for repo format v0")
                safe_delete_file(version_file)
            create_file(version_file, "1")
        except OSError, e:
            raise UserError("Upgrade could not complete. Make sure that the repository "+
                            "root is writable and try again. The error was: '%s'" % e)

    def __upgrade_repo_v1(self):
        """ This upgrade will perform the following actions:
        * If it exists, delete file "derived/sha256/sha256cache"
        * Rmdir directory "derived/sha256"
        * Update "version.txt" to 2
        """
        assert not self.readonly, "Repo is read only, cannot upgrade"
        version = self.__get_repo_version()
        assert version == 1
        if not isWritable(self.repopath):
            raise UserError("Cannot upgrade repository - write protected")
        try:
            for directory in REPO_DIRS_V1:
                integrity_assert(dir_exists(os.path.join(self.repopath, directory)), \
                                     "Repository says it is v1 format but is missing %s" % directory)
            dbfile = os.path.join(self.repopath, DERIVED_SHA256_DIR, "sha256cache")
            sha256_dir = os.path.join(self.repopath, DERIVED_SHA256_DIR)
            if os.path.exists(dbfile):
                # recipes_dir is an experimental feature and should not contain
                # any data in a v0 repo (if it exists at all)
                safe_delete_file(dbfile)
            if os.path.exists(sha256_dir):
                os.rmdir(sha256_dir)
            replace_file(os.path.join(self.repopath, VERSION_FILE), "2")
        except OSError, e:
            raise UserError("Upgrade could not complete. Make sure that the repository "+
                            "root is writable and try again. The error was: '%s'" % e)

    def __upgrade_repo_v2(self):
        """ This upgrade will perform the following actions:
        * Update "version.txt" to 3
        * Restore any legally missing snapshots with a deleted snapshot definition.
        """
        assert not self.readonly, "Repo is read only, cannot upgrade"
        version = self.__get_repo_version()
        assert version == 2
        if not isWritable(self.repopath):
            raise UserError("Cannot upgrade repository - write protected")
        for directory in REPO_DIRS_V2:
            integrity_assert(dir_exists(os.path.join(self.repopath, directory)), \
                                 "Repository says it is v2 format but is missing %s" % directory)
        for rev in range(1, self.get_highest_used_revision() + 1):
            if os.path.exists(self.get_session_path(rev)):
                continue
            tmpdir = tempfile.mkdtemp(prefix = "tmp_", dir = os.path.join(self.repopath, TMP_DIR))
            writer = sessions._NaiveSessionWriter(session_name = u"__deleted", base_session = None, path = tmpdir)
            writer.set_fingerprint("d41d8cd98f00b204e9800998ecf8427e")
            writer.commit()
            del writer
            os.rename(tmpdir, self.get_session_path(rev))
        try:
            replace_file(os.path.join(self.repopath, RECOVERYTEXT_FILE), recoverytext)
            replace_file(os.path.join(self.repopath, VERSION_FILE), "3")
        except OSError, e:
            raise UserError("Upgrade could not complete. Make sure that the repository "+
                            "root is writable and try again. The error was: '%s'" % e)

    def get_path(self, subdir, *parts):
        return os.path.join(self.repopath, subdir, *parts)
        
    def __get_repo_version(self):
        version_file = os.path.join(self.repopath, VERSION_FILE)
        if os.path.exists(version_file):
            with safe_open(version_file, "rb") as f:
                return int(f.read())
        # Repo is from before repo format numbering started.
        # Make sure it is a valid one and return v0
        for directory in REPO_DIRS_V0:
            integrity_assert(dir_exists(os.path.join(self.repopath, directory)), 
                             "The repo at %s does not look like a repository (missing %s)" % (self.repopath, directory))
        return 0

    def __str__(self):
        return "repo:"+self.repopath

    def get_repo_path(self):
        return self.repopath

    def get_queue_path(self, session_id):
        assert isinstance(session_id, int)
        return os.path.join(self.repopath, QUEUE_DIR, str(session_id))

    def get_blob_path(self, sum):
        assert is_md5sum(sum), "Was: %s" % (sum)
        return os.path.join(self.repopath, BLOB_DIR, sum[0:2], sum)

    def get_recipe_path(self, recipe):
        if is_recipe_filename(recipe):
            recipe = recipe.split(".")[0]
        assert is_md5sum(recipe)
        return os.path.join(self.repopath, RECIPES_DIR, recipe + ".recipe")

    def has_raw_blob(self, sum):
        """Returns true if there is an actual (non-recipe based)
        blob with the given checksum"""
        blobpath = self.get_blob_path(sum)
        return os.path.exists(blobpath)

    def has_recipe_blob(self, sum):
        return os.path.exists(self.get_recipe_path(sum))

    def has_blob(self, sum):
        """Returns true if there is a blob with the given
        checksum. The blob may be raw or recipe-based."""
        blobpath = self.get_blob_path(sum)
        recpath = self.get_recipe_path(sum)
        return os.path.exists(blobpath) or os.path.exists(recpath)

    def get_recipe(self, sum):
        recpath = self.get_recipe_path(sum)
        if not os.path.exists(recpath):
            return None
        recipe = read_json(f)
        return recipe

    def get_blob_size(self, sum):
        blobpath = self.get_blob_path(sum)
        if os.path.exists(blobpath):
            # Windows always returns a Long. Let's be consistent.
            return long(os.path.getsize(blobpath))
        recipe = self.get_recipe(sum)
        if not recipe:
            raise ValueError("No such blob or recipe exists: "+sum)
        return long(recipe['size'])

    def get_blob_reader(self, sum, offset = 0, size = -1):
        if self.has_raw_blob(sum):
            blobsize = self.get_blob_size(sum)
            if size == -1:
                size = blobsize
            assert blobsize <= offset + size
            path = self.get_blob_path(sum)
            fo = safe_open(path, "rb")
            fo.seek(offset)
            return FileDataSource(fo, size)
        recipe = self.get_recipe(sum)
        if recipe:
            assert False, "Recipes not implemented yet"
        raise ValueError("No such blob or recipe exists: "+sum)

    def get_blob(self, sum, offset = 0, size = -1):
        """ Returns None if there is no such blob """
        if self.has_raw_blob(sum):
            path = self.get_blob_path(sum)
            with safe_open(path, "rb") as f:
                f.seek(offset)
                data = f.read(size)
            return data
        recipe = self.get_recipe(sum)
        if recipe:
            reader = create_blob_reader(recipe, self)
            reader.seek(offset)
            return reader.read(size)
        else:
            raise ValueError("No such blob or recipe exists: "+sum)

    def get_session_path(self, session_id):
        assert isinstance(session_id, int)
        return os.path.join(self.repopath, SESSIONS_DIR, str(session_id))

        
    def get_all_sessions(self):
        return get_all_ids_in_directory(self.get_path(SESSIONS_DIR))

    def is_deleted(self, rev):
        return self.get_session(rev).is_deleted()

    def get_deleted_snapshots(self):
        result = []
        for sid in self.get_all_sessions():
            if self.get_session(sid).is_deleted():
                result.append(sid)
        return result

    def get_highest_used_revision(self):
        """ Returns the highest used revision id in the
        repository. Deleted revisions are counted as well. Note that
        this method returns 0 in the case that there are no
        revisions. """
        existing_sessions = get_all_ids_in_directory(self.get_path(SESSIONS_DIR))
        return max([0] + existing_sessions)

    def has_snapshot(self, id):
        assert isinstance(id, int)
        path = os.path.join(self.repopath, SESSIONS_DIR, str(id))
        return os.path.exists(path)

    def verify_snapshot(self, id):
        if self.__get_repo_version() < 3: # To make it possible to access old read-only repos
            warn("todo: implement verify_snapshot for early versions")
            return True
        session_exists = self.has_snapshot(id)
        if not session_exists:
            raise CorruptionError("Snapshot %s is missing" % id)
        snapshot = self.get_session(id)
        # No exception - all is well

    def get_session(self, id):
        assert id, "Id was: "+ str(id)
        assert isinstance(id, int)
        misuse_assert(self.has_snapshot(id), "There is no snapshot with id %s" % id)
        if id not in self.session_readers:
            self.session_readers[id] = sessions.SessionReader(self, self.get_session_path(id))
        return self.session_readers[id]

    def create_session(self, session_name, base_session = None, session_id = None):
        misuse_assert(not self.readonly, "Cannot create a session in a write protected repo")
        assert isinstance(session_name, unicode)
        assert base_session == None or isinstance(base_session, int)
        assert session_id == None or isinstance(session_id, int)
        return sessions.SessionWriter(self, session_name = session_name, \
                                          base_session = base_session, \
                                          session_id = session_id)

    def find_last_revision(self, session_name):
        """ Returns the id of the latest snapshot in the specified
        session. Returns None if there is no such session. """
        assert isinstance(session_name, unicode)
        all_sids = self.get_all_sessions()
        all_sids.sort()
        all_sids.reverse()
        for sid in all_sids:
            session = self.get_session(sid)
            name = session.get_client_value("name")
            if name == session_name:
                return sid
        return None

    def find_next_session_id(self):
        return self.get_highest_used_revision() + 1

    def get_blob_names(self):
        blobpattern = re.compile("/([0-9a-f]{32})$")
        assert blobpattern.search("b5/b5fb453aeaaef8343353cc1b641644f9")
        tree = get_tree(os.path.join(self.repopath, BLOB_DIR))
        matches = set()
        for f in tree:
            m = blobpattern.search(f)
            if m:
                matches.add(m.group(1))
        return list(matches)

    def get_orphan_blobs(self):
        used_blobs = set()
        for sid in self.get_all_sessions():
            snapshot = self.get_session(sid)
            for blobinfo in snapshot.get_raw_bloblist():
                if 'md5sum' in blobinfo:
                    used_blobs.add(blobinfo['md5sum'])
        if self.get_queued_session_id():
            # Must ensure that any queued new snapshot is considered as well
            queued_session = sessions.SessionReader(None, self.get_path(QUEUE_DIR, str(self.get_queued_session_id())))
            for blobinfo in queued_session.get_raw_bloblist():
                if 'md5sum' in blobinfo:
                    used_blobs.add(blobinfo['md5sum'])
        orphans = set(self.get_blob_names()) - used_blobs
        return orphans

    def verify_blob(self, sum):
        recipe = self.get_recipe(sum)
        if recipe:
            assert False, "recipes not implemented"
            #reader = create_blob_reader(recipe, self)
            #verified_ok = (sum == md5sum_file(reader))
        if not self.has_raw_blob(sum):
            raise ValueError("No such blob or recipe: " + sum)
        path = self.get_blob_path(sum)
        with safe_open(path, "rb") as f:
            md5_summer = hashlib.md5()
            for block in file_reader(f):
                md5_summer.update(block)
            md5 = md5_summer.hexdigest()
            verified_ok = (sum == md5)
        return verified_ok 

    def find_redundant_raw_blobs(self):
        all_blobs = self.get_blob_names()
        for blob in all_blobs:
            if self.has_recipe_blob(blob) and self.has_raw_blob(blob):
                yield blob

    def get_queued_session_id(self):
        path = os.path.join(self.repopath, QUEUE_DIR)
        files = os.listdir(path)
        assert len(files) <= 1, "Corrupted queue directory - more than one item in queue"
        if len(files) == 0:
            return None
        result = int(files[0])
        assert result > 0, "Corrupted queue directory - illegal session id"
        return result

    def consolidate_snapshot(self, session_path, forced_session_id = None):
        assert isinstance(session_path, unicode)
        assert forced_session_id == None or isinstance(forced_session_id, int)
        assert not self.readonly, "Cannot consolidate because repo is read-only"
        self.repo_mutex.lock_with_timeout(60)
        try:
            return self.__consolidate_snapshot(session_path, forced_session_id)
        finally:
            self.repo_mutex.release()

    def __consolidate_snapshot(self, session_path, forced_session_id):
        assert isinstance(session_path, unicode)
        assert self.repo_mutex.is_locked()
        assert not self.get_queued_session_id()
        assert not self.readonly, "Cannot consolidate because repo is read-only"
        if forced_session_id:
            session_id = forced_session_id
        else:
            session_id = self.find_next_session_id()
        assert session_id > 0
        assert session_id not in self.get_all_sessions()
        queue_dir = self.get_queue_path(session_id)
        assert not os.path.exists(queue_dir), "Queue entry collision: %s" % queue_dir
        shutil.move(session_path, queue_dir)
        self.process_queue()
        return session_id

    def get_referring_snapshots(self, rev):
        """ Returns a (possibly empty) list of all the snapshots that
        has the given rev as base snapshot. """
        assert isinstance(rev, int)
        result = []
        for sid in self.get_all_sessions():
            snapshot = self.get_session(sid)
            if snapshot.get_base_id() == rev:
                result.append(rev)
        return result

    def __erase_snapshots(self, snapshot_ids):
        assert self.repo_mutex.is_locked()
        if not snapshot_ids:
            # Avoid check for erase permissions if not erasing anything
            return
        if not self.allows_permanent_erase():
            raise MisuseError("Not allowed for this repo")
        misuse_assert(not self.readonly, "Cannot erase snapshots from a write protected repo")
        snapshot_ids = map(int, snapshot_ids) # Make sure there are only ints here
        snapshot_ids.sort()
        snapshot_ids.reverse()

        trashdir = tempfile.mkdtemp(prefix = "TRASH_erased_snapshots_", dir = self.get_path(TMP_DIR))
        for rev in snapshot_ids:
            try:
                self.__erase_snapshot(rev, trashdir)
            except OSError, e:
                if e.errno == 13:
                    raise UserError("Snapshot %s is write protected, cannot erase. Change your repository file permissions and try again." % rev)

    def __erase_snapshot(self, rev, trashdir):
        # Carefully here... We must allow for a resumed operation 
        if not self.allows_permanent_erase():
            raise MisuseError("Not allowed for this repo")
        misuse_assert(not self.readonly, "Cannot erase snapshots from a write protected repo")
        if self.get_referring_snapshots(rev):
            raise MisuseError("Erasing rev %s would create orphan snapshots" % rev)
        if rev in self.session_readers:
            del self.session_readers[rev]

        session_path = self.get_session_path(rev)
        delete_copy = os.path.join(session_path, "deleted")
        if not os.path.exists(delete_copy):
            tmpcopy = tempfile.mktemp(prefix ="deleted_", dir = self.get_path(TMP_DIR))
            shutil.copytree(session_path, tmpcopy)
            os.rename(tmpcopy, delete_copy)

        session_data = read_json(os.path.join(delete_copy, "session.json"))        

        for filename in "session.json", "bloblist.json", "session.md5", session_data['fingerprint'] + ".fingerprint":
            full_path = os.path.join(session_path, filename)
            if os.path.exists(full_path):
                os.unlink(full_path)

        _snapshot_delete_test_hook(rev)

        writer = sessions._NaiveSessionWriter(session_name = u"__deleted", base_session = None, path = session_path)
        writer.delete(deleted_session_name = session_data['client_data']['name'], deleted_fingerprint = session_data['fingerprint'])
        writer.set_fingerprint("d41d8cd98f00b204e9800998ecf8427e")
        writer.commit()
        os.rename(delete_copy, os.path.join(trashdir, str(rev) + ".deleted"))

    def erase_orphan_blobs(self):
        assert self.repo_mutex.is_locked()
        if not self.allows_permanent_erase():
            raise MisuseError("Not allowed for this repo")
        misuse_assert(not self.readonly, "Cannot erase blobs from a write protected repo")
        orphan_blobs = self.get_orphan_blobs()
        trashdir = tempfile.mkdtemp(prefix = "TRASH_erased_blobs_", dir = self.get_path(TMP_DIR))
        for blob in orphan_blobs:
            os.rename(self.get_blob_path(blob), os.path.join(trashdir, blob))
        return len(orphan_blobs)

    def process_queue(self):
        assert self.repo_mutex.is_locked()
        assert not self.readonly, "Repo is read only, cannot process queue"
        session_id = self.get_queued_session_id()
        if session_id == None:
            return
        queued_item = self.get_queue_path(session_id)
        items = os.listdir(queued_item)

        # Check the checksums of all blobs
        for filename in items:
            if not is_md5sum(filename):
                continue
            blob_path = os.path.join(queued_item, filename)
            assert filename == md5sum_file(blob_path), "Invalid blob found in queue dir:" + blob_path
    
        # Check the existence of all required files
        # TODO: check the contents for validity
        meta_info = read_json(os.path.join(queued_item, "session.json"))
        
        contents = os.listdir(queued_item)
        snapshots_to_delete = []

        # Check that there are no unexpected files in the snapshot,
        # and perform a simple test for json well-formedness
        for filename in contents:
            if is_md5sum(filename): 
                continue # Blob
            if filename == meta_info['fingerprint']+".fingerprint":
                continue # Fingerprint file
            if filename in ["session.json", "bloblist.json"]:
                read_json(os.path.join(queued_item, filename)) # Check if malformed
                continue
            if filename in ["session.md5"]:
                continue
            if is_recipe_filename(filename):
                read_json(os.path.join(queued_item, filename)) # Check if malformed
                continue
            if filename == "delete.json":
                snapshots_to_delete = read_json(os.path.join(queued_item, "delete.json"))
                continue
            assert False, "Unexpected file in new session:" + filename

        # Check that all necessary files are present in the snapshot
        assert set(contents) >= \
            set([meta_info['fingerprint']+".fingerprint",\
                     "session.json", "bloblist.json", "session.md5"]), \
                     "Missing files in queue dir: "+str(contents)

        # Everything seems OK, move the blobs and consolidate the session
        for filename in items:
            if is_md5sum(filename):
                blob_to_move = os.path.join(queued_item, filename)
                destination_path = self.get_blob_path(filename)
                # Check for existence before moving. Another
                # snapshot might have checked in this same file
                # concurrently, see issue 70.
                if os.path.exists(destination_path):
                    os.remove(blob_to_move)
                else:
                    move_file(blob_to_move, destination_path, mkdirs = True)
            elif is_recipe_filename(filename):
                recipe_to_move = os.path.join(queued_item, filename)
                destination_path = self.get_recipe_path(filename)
                move_file(recipe_to_move, destination_path, mkdirs = True)
            else:
                pass # The rest becomes a snapshot definition directory

        if snapshots_to_delete:
            # Intentionally redundant check for erase enable flag
            assert os.path.exists(os.path.join(self.repopath, "ENABLE_PERMANENT_ERASE"))
            self.__erase_snapshots(snapshots_to_delete)
        if os.path.exists(os.path.join(queued_item, "delete.json")):
            self.erase_orphan_blobs()
            safe_delete_file(os.path.join(queued_item, "delete.json"))

        session_path = os.path.join(self.repopath, SESSIONS_DIR, str(session_id))
        assert not os.path.exists(session_path), "Session path already exists: %s" % session_path
        shutil.move(queued_item, session_path)
        assert not self.get_queued_session_id(), "Commit completed, but queue should be empty after processing"


def get_all_ids_in_directory(path):
    result = []
    for dir in os.listdir(path):
        if re.match("^[0-9]+$", dir) != None:
            assert int(dir) > 0, "No session 0 allowed in repo"
            result.append(int(dir))
    assert len(result) == len(set(result))
    result.sort()
    return result

def _snapshot_delete_test_hook(rev):
    """ This method is intended to be replaced during testing to
    simulate an interrupted operation."""
    pass
