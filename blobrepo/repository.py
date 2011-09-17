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
import derived

#TODO: use/modify the session reader so that we don't have to use json here
import sys
from common import *
from boar_common import *
from blobreader import create_blob_reader
from jsonrpc import FileDataSource
from boar_exceptions import UserError

VERSION_FILE = "version.txt"
RECOVERYTEXT_FILE = "recovery.txt"
QUEUE_DIR = "queue"
BLOB_DIR = "blobs"
SESSIONS_DIR = "sessions"
RECIPES_DIR = "recipes"
TMP_DIR = "tmp"
DERIVED_DIR = "derived"
DERIVED_SHA256_DIR = "derived/sha256"
DERIVED_BLOCKS_DIR = "derived/blocks"

REPO_DIRS_V0 = (QUEUE_DIR, BLOB_DIR, SESSIONS_DIR, RECIPES_DIR, TMP_DIR)
REPO_DIRS_V1 = (QUEUE_DIR, BLOB_DIR, SESSIONS_DIR, RECIPES_DIR, TMP_DIR,\
    DERIVED_DIR, DERIVED_SHA256_DIR, DERIVED_BLOCKS_DIR)

recoverytext = """Repository format v1

This is a versioned repository of files. It is designed to be easy to
recover in case the original software is unavailable. This document
describes the layout of the repository, so that a programmer can
construct a simple program that recovers the data.

All files are stored verbatim in the "blobs" directory, named after
their md5 checksum, and sorted in sub directories based on the start
of their names. For instance, if a file "testimage.jpg" has the
checksum bc7b0fb8c2e096693acacbd6cb070f16, it will be stored in
blobs/bc/bc7b0fb8c2e096693acacbd6cb070f16 since the checksum starts
with the letters "bc". The filename "testimage.jpg" is discarded. The
information necessary to reconstruct a file tree is stored in a
session file.

The individual sessions are stored in the "sessions" sub
directory. Each session represents a point in time for a file
tree. The session directory contains two files, bloblist.json and
session.json. See RFC4627 for details on the json file format. For
each entry in the list of blobs, a filename and a md5 checksum is
stored. 

To restore a session, iterate over the bloblist and copy the blob with
the corresponding checksum to a file with the name specified in the
bloblist.

"""

class MisuseError(Exception):
    def __init__(self, msg):
        Exception.__init__(self, msg)

class CorruptionError(Exception):
    """A serious integrity problem of the repository that cannot be
    repaired automatically, if at all."""
    def __init__(self, msg):
        Exception.__init__(self, msg)

class SoftCorruptionError(Exception):
    """A harmless integrity problem of the repository requiring
    rebuilding of derived information."""
    def __init__(self, msg):
        Exception.__init__(self, msg)

def misuse_assert(test, errormsg = None):
    if not test:
        raise MisuseError(errormsg)

def integrity_assert(test, errormsg = None):
    if not test:
        raise CorruptionError(errormsg)

def create_repository(repopath):
    os.mkdir(repopath)
    create_file(os.path.join(repopath, VERSION_FILE), "1")
    os.mkdir(os.path.join(repopath, QUEUE_DIR))
    os.mkdir(os.path.join(repopath, BLOB_DIR))
    os.mkdir(os.path.join(repopath, SESSIONS_DIR))
    os.mkdir(os.path.join(repopath, RECIPES_DIR))
    os.mkdir(os.path.join(repopath, TMP_DIR))
    os.mkdir(os.path.join(repopath, DERIVED_DIR))
    os.mkdir(os.path.join(repopath, DERIVED_SHA256_DIR))
    os.mkdir(os.path.join(repopath, DERIVED_BLOCKS_DIR))
    with open(os.path.join(repopath, "recovery.txt"), "w") as f:
        f.write(recoverytext)

def is_recipe_filename(filename):
    filename_parts = filename.split(".")
    return len(filename_parts) == 2 \
        and filename_parts[1] == "recipe" \
        and is_md5sum(filename_parts[0])
            



class Repo:
    def __init__(self, repopath):
        # The path must be absolute to avoid problems with clients
        # that changes the cwd. For instance, fuse.
        assert(os.path.isabs(repopath)), "The repo path must be absolute. "\
            +"Was: " + repopath
        self.repopath = unicode(repopath)
        self.session_readers = {}
        self.repo_mutex = FileMutex(os.path.join(repopath, TMP_DIR), "__REPOLOCK__")
        misuse_assert(os.path.exists(self.repopath), "No such directory: %s" % (self.repopath))
        self.repo_mutex.lock_with_timeout(60)
        try:
            self.__upgrade_repo()
            self.__quick_check()
            self.sha256 = derived.blobs_sha256(self, self.repopath + "/derived/sha256")
            self.process_queue()
        finally:
            self.repo_mutex.release()

    def close(self):
        self.sha256.close()

    def __quick_check(self):
        """This method must be called after any repository upgrade
        procedure. It will assert that the repository is upgraded to
        the latest format and looks somewhat ok. It will raise an
        exception if an error is found."""
        repo_version = self.__get_repo_version()
        assert repo_version, "Repo format obsolete. Upgrade failed?"
        integrity_assert(repo_version == 1, ("Repo version %s can not be handled by this version of boar" % repo_version))
        assert_msg = "Repository at %s is missing vital files. (Is it really a repository?)" % self.repopath
        for directory in REPO_DIRS_V1:
            integrity_assert(dir_exists(os.path.join(self.repopath, directory)), assert_msg)

    def __upgrade_repo(self):
        version = self.__get_repo_version()
        if version > 1:
            raise UserError("Repo version %s can not be handled by this version of boar" % version)
        if version == 1:
            return
        notice("Old repo format detected. Upgrading...")
        assert version == 0
        version_file = os.path.join(self.repopath, VERSION_FILE)
        assert self.repo_mutex.locked
        for directory in (DERIVED_DIR, DERIVED_SHA256_DIR, DERIVED_BLOCKS_DIR):
            if dir_exists(self.repopath + "/" + directory):
                warn("Repo upgrade confusion: a folder already existed while upgrading to v1: %s" % directory)
                continue
            notice("Upgrading repo - creating '%s' dir" % directory)
            os.mkdir(self.repopath + "/" + directory)


        try:
            safe_delete_file(os.path.join(self.repopath, RECOVERYTEXT_FILE))
        except OSError:
            # Missing non-essential file should not be fatal
            warn("Repo did not contain a recovery.txt")
        create_file(os.path.join(self.repopath, RECOVERYTEXT_FILE), recoverytext)

        if os.path.exists(version_file):
            warn("Version marker should not exist for repo format v0")
            safe_delete_file(version_file)
        create_file(version_file, "1")

        try:
            self.__quick_check()
        except:
            warn("Post-upgrade quickcheck of repository failed!")
            raise

    def __get_repo_version(self):
        version_file = os.path.join(self.repopath, VERSION_FILE)
        if os.path.exists(version_file):
            with open(version_file, "r") as f:
                return int(f.read())
        # Repo is from before repo format numbering started.
        # Make sure it is a valid one and return v0
        for directory in REPO_DIRS_V0:
            integrity_assert(dir_exists(os.path.join(self.repopath, directory)), 
                             "The repo at %s does not look like a repository" % self.repopath)
        for directory in (DERIVED_DIR, DERIVED_SHA256_DIR):
            integrity_assert(not dir_exists(os.path.join(self.repopath, directory)),
                             "Repo %s does not seem to match repository contents" % VERSION_FILE)
        return 0

    def __str__(self):
        return "repo:"+self.repopath

    def get_repo_path(self):
        return self.repopath

    def get_queue_path(self, filename):
        return os.path.join(self.repopath, QUEUE_DIR, filename)

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
            return os.path.getsize(blobpath)
        recipe = self.get_recipe(sum)
        if not recipe:
            raise ValueError("No such blob or recipe exists: "+sum)
        return recipe['size']

    def get_blob_sha256(self, sum):
        return self.sha256.get_sha256(sum)

    def get_blob_reader(self, sum, offset = 0, size = -1):
        if self.has_raw_blob(sum):
            blobsize = self.get_blob_size(sum)
            if size == -1:
                size = blobsize
            assert blobsize <= offset + size
            path = self.get_blob_path(sum)
            fo = open(path, "rb")
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
            with open(path, "rb") as f:
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
        return os.path.join(self.repopath, SESSIONS_DIR, str(session_id))

    def get_all_sessions(self):
        session_dirs = []
        for dir in os.listdir(os.path.join(self.repopath, SESSIONS_DIR)):
            if re.match("^[0-9]+$", dir) != None:
                assert int(dir) > 0, "No session 0 allowed in repo"
                session_dirs.append(int(dir))
        session_dirs.sort()
        return session_dirs

    def has_snapshot(self, id):
        path = os.path.join(self.repopath, SESSIONS_DIR, str(id))
        return os.path.exists(path)

    def get_session(self, id):
        assert id, "Id was: "+ str(id)
        misuse_assert(self.has_snapshot(id), "There is no snapshot with id %s" % id)
        if id not in self.session_readers:
            self.session_readers[id] = sessions.SessionReader(self, self.get_session_path(id))
        return self.session_readers[id]

    def create_session(self, session_name, base_session = None, session_id = None):
        return sessions.SessionWriter(self, session_name = session_name, \
                                          base_session = base_session, \
                                          session_id = session_id)

    def find_last_revision(self, session_name):
        """ Returns the id of the latest snapshot in the specified
        session. Returns None if there is no such session. """
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
        assert os.path.exists(self.repopath)
        session_dirs = self.get_all_sessions()
        session_dirs.append(0)
        return max(session_dirs) + 1            

    def get_blob_names(self):
        blobpattern = re.compile("/([0-9a-f]{32})$")
        assert blobpattern.search("b5/b5fb453aeaaef8343353cc1b641644f9")
        tree = get_tree(os.path.join(self.repopath, BLOB_DIR))
        matches = set()
        for f in tree:
            m = blobpattern.search(f)
            if m:
                matches.add(m.group(1))
        blobpattern = re.compile("([0-9a-f]{32})\\.recipe$")
        tree = get_tree(os.path.join(self.repopath, RECIPES_DIR))
        for f in tree:
            m = blobpattern.search(f)
            if m:
                matches.add(m.group(1))
        return list(matches)

    def verify_blob(self, sum):
        recipe = self.get_recipe(sum)
        if recipe:
            reader = create_blob_reader(recipe, self)
            verified_ok = (sum == md5sum_file(reader))
        elif self.has_raw_blob(sum):
            path = self.get_blob_path(sum)
            verified_ok = (sum == md5sum_file(path))
        else:
            raise ValueError("No such blob or recipe: " + sum)
        return verified_ok 

    def find_redundant_raw_blobs(self):
        all_blobs = self.get_blob_names()
        for blob in all_blobs:
            if self.has_recipe_blob(blob) and self.has_raw_blob(blob):
                yield blob

    def isIdentical(self, other_repo):
        """ Returns True iff the other repo contains the same sessions
        with the same fingerprints as this repo."""
        if not other_repo.isContinuation(self):
            return False
        return set(self.get_all_sessions()) == set(other_repo.get_all_sessions())

    def isContinuation(self, other_repo):
        """ Returns True if the other repo is a continuation of this
        one. That is, the other repo contains all the sessions of this
        repo, and then zero of more additional sessions."""
        if set(self.get_all_sessions()) > set(other_repo.get_all_sessions()):
            # Not same sessions - cannot be successor
            return False
        for session_id in self.get_all_sessions():
            self_session = self.get_session(session_id)
            other_session = other_repo.get_session(session_id)
            if self_session.get_fingerprint() != other_session.get_fingerprint():
                return False
        return True

    def pullFrom(self, other_repo):
        """Updates this repository with changes from the other
        repo. The other repo must be a continuation of this repo."""
        print "Pulling updates from %s into %s" % (other_repo, self)
        # Check that other repo is a continuation of this one
        assert self.isContinuation(other_repo), \
            "Cannot pull: %s is not a continuation of %s" % (other_repo, self)

        # Copy all new blobs
        self_blobs = set(self.get_blob_names())
        other_blobs = set(other_repo.get_blob_names())
        assert set(self_blobs) <= set(other_blobs), \
            "Other repo is missing some blobs that are present in this repo. Corrupt repository?"

        for blobname in other_blobs - self_blobs:
            assert other_repo.has_raw_blob(blobname), "Cloning of recipe blobs not yet implemented"

        # Copy all new sessions
        self_sessions = set(self.get_all_sessions())
        other_sessions = set(other_repo.get_all_sessions())
        sessions_to_copy = list(other_sessions - self_sessions)
        sessions_to_copy.sort()
        for session_id in sessions_to_copy:
            reader = other_repo.get_session(session_id)
            base_session = reader.get_properties().get('base_session', None)
            writer = self.create_session(reader.get_properties()['client_data']['name'], base_session, session_id)
            writer.commitClone(reader)

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
        self.repo_mutex.lock_with_timeout(60)
        try:
            return self.__consolidate_snapshot(session_path, forced_session_id)
        finally:
            self.repo_mutex.release()

    def __consolidate_snapshot(self, session_path, forced_session_id):
        assert self.repo_mutex.is_locked()
        assert not self.get_queued_session_id()
        if forced_session_id: 
            session_id = forced_session_id
        else:
            session_id = self.find_next_session_id()
        assert session_id > 0
        assert session_id not in self.get_all_sessions()
        queue_dir = self.get_queue_path(str(session_id))
        shutil.move(session_path, queue_dir)
        self.process_queue()
        return session_id

    def process_queue(self):
        assert self.repo_mutex.is_locked()
        session_id = self.get_queued_session_id()
        if session_id == None:
            return
        queued_item = self.get_queue_path(str(session_id))
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
                move_file(blob_to_move, destination_path, mkdirs = True)
            elif is_recipe_filename(filename):
                recipe_to_move = os.path.join(queued_item, filename)
                destination_path = self.get_recipe_path(filename)
                move_file(recipe_to_move, destination_path, mkdirs = True)
            else:
                pass # The rest becomes a snapshot definition directory

        session_path = os.path.join(self.repopath, SESSIONS_DIR, str(session_id))
        shutil.move(queued_item, session_path)
        assert not self.get_queued_session_id(), "Commit completed, but queue should be empty after processing"


