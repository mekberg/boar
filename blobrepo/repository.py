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

#TODO: use/modify the session reader so that we don't have to use json here
import sys
if sys.version_info >= (2, 6):
    import json
else:
    import simplejson as json

from common import *
from blobreader import create_blob_reader
from jsonrpc import FileDataSource

QUEUE_DIR = "queue"
BLOB_DIR = "blobs"
SESSIONS_DIR = "sessions"
RECIPES_DIR = "recipes"
TMP_DIR = "tmp"

recoverytext = """Repository format 0.1

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

class MisuseException(Exception):
    pass

def create_repository(repopath):
    os.mkdir(repopath)
    os.mkdir(os.path.join(repopath, QUEUE_DIR))
    os.mkdir(os.path.join(repopath, BLOB_DIR))
    os.mkdir(os.path.join(repopath, SESSIONS_DIR))
    os.mkdir(os.path.join(repopath, RECIPES_DIR))
    os.mkdir(os.path.join(repopath, TMP_DIR))
    with open(os.path.join(repopath, "recovery.txt"), "w") as f:
        f.write(recoverytext)
    
class Repo:
    def __init__(self, repopath):
        # The path must be absolute to avoid problems with clients
        # that changes the cwd. For instance, fuse.
        assert(os.path.isabs(repopath)), "The repo path must be absolute. "\
            +"Was: " + repopath
        self.repopath = unicode(repopath)
        self.session_readers = {}
        assert os.path.exists(self.repopath), "No such directory: %s" % (self.repopath)
        assert os.path.exists(self.repopath + "/sessions")
        assert os.path.exists(self.repopath + "/blobs")
        assert os.path.exists(self.repopath + "/tmp")
        self.process_queue()

    def __str__(self):
        return "repo:"+self.repopath

    def get_repo_path(self):
        return self.repopath

    def get_queue_path(self, filename):
        return os.path.join(self.repopath, QUEUE_DIR, filename)

    def get_blob_path(self, sum):
        assert is_md5sum(sum), "Was: %s" % (sum)
        return os.path.join(self.repopath, BLOB_DIR, sum[0:2], sum)

    def get_recipe_path(self, sum):
        assert is_md5sum(sum)
        return os.path.join(self.repopath, RECIPES_DIR, sum + ".recipe")

    def has_raw_blob(self, sum):
        """Returns true if there is an actual (non-recipe based)
        blob with the given checksum"""
        blobpath = self.get_blob_path(sum)
        return os.path.exists(blobpath)

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
        with open(recpath) as f:
            recipe = json.load(f)
        return recipe

    def get_blob_size(self, sum):
        blobpath = self.get_blob_path(sum)
        if os.path.exists(blobpath):
            return os.path.getsize(blobpath)
        recipe = self.get_recipe(sum)
        if not recipe:
            raise ValueError("No such blob or recipe exists: "+sum)
        return recipe['size']

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

    def get_session(self, id):
        assert id, "Id was: "+ str(id)
        if id not in self.session_readers:
            self.session_readers[id] = sessions.SessionReader(self, self.get_session_path(id))
        return self.session_readers[id]

    def create_session(self, base_session = None, session_id = None):
        return sessions.SessionWriter(self, base_session = base_session, session_id = session_id)

    def find_next_session_id(self):
        assert os.path.exists(self.repopath)
        session_dirs = self.get_all_sessions()
        session_dirs.append(0)
        return max(session_dirs) + 1            

    def verify_all(self):
        for sid in self.get_all_sessions():
            session = sessions.SessionReader(self, sid)
            session.verify()

    def get_blob_names(self):
        blobpattern = re.compile("/([0-9a-f]{32})$")
        assert blobpattern.search("b5/b5fb453aeaaef8343353cc1b641644f9")
        tree = get_tree(os.path.join(self.repopath, BLOB_DIR))
        matches = []
        for f in tree:
            m = blobpattern.search(f)
            if m:
                matches.append(m.group(1))
        blobpattern = re.compile("([0-9a-f]{32})\\.recipe$")
        tree = get_tree(os.path.join(self.repopath, RECIPES_DIR))
        for f in tree:
            m = blobpattern.search(f)
            if m:
                matches.append(m.group(1))
        return matches

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
            writer = self.create_session(base_session, session_id)
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

    def process_queue(self):
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
        with open(os.path.join(queued_item, "session.json"), "rb") as f:
            meta_info = json.load(f)
        contents = [x for x in os.listdir(queued_item) if not is_md5sum(x)]
        assert set(contents) == \
            set([meta_info['fingerprint']+".fingerprint",\
                     "session.json", "bloblist.json", "session.md5"]), \
                     "Missing or unexpected files in queue dir: "+str(contents)

        # Everything seems OK, move the blobs and consolidate the session
        for filename in items:
            if not is_md5sum(filename):
                continue
            blob_to_move = os.path.join(queued_item, filename)
            destination_path = self.get_blob_path(filename)
            assert not os.path.exists(destination_path)
            dir = os.path.dirname(destination_path)
            if not os.path.exists(dir):
                os.makedirs(dir)
            os.rename(blob_to_move, destination_path)
            #print "Moving", os.path.join(queued_item, filename),"to", destination_path

        session_path = os.path.join(self.repopath, SESSIONS_DIR, str(session_id))
        shutil.move(queued_item, session_path)
        assert not self.get_queued_session_id(), "Commit completed, but queue should be empty after processing"
        #print "Done"
