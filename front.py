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

""" The Front class serves two important purposes. First, it is the
API of boar. All interaction with a repository must happen through
this interface. Secondly, all arguments and return values are
primitive values that can be serialized easily, which makes it easy to
implement an RPC mechanism for this interface.
"""

from blobrepo import repository
from boar_exceptions import *
import sys
from time import ctime, time
from common import md5sum, is_md5sum, warn
from blobrepo.sessions import bloblist_fingerprint

if sys.version_info >= (2, 6):
    import json
else:
    import simplejson as json
import base64

def get_file_contents(front, session_name, file_name):
    """This is a convenience function to get the full contents of a
    named file from the latest revision of a named session. It must
    only be used on files that are known to be of a reasonable
    size. The session must exist or an SessionNotFoundError will the
    thrown. If there is a session, but no matching file, None is
    returned."""
    rev = front.find_last_revision(session_name)
    if not rev:
        raise SessionNotFoundError("No such session: %s" % session_name)
    for blobinfo in front.get_session_bloblist(rev):
        if blobinfo['filename'] == file_name:
            blob_reader = front.get_blob(blobinfo['md5sum'])
            return blob_reader.read()
    return None

def add_file_simple(front, filename, contents):
    """Adds a file with contents to a new snapshot. The front instance
    "create_session()" must have been called before this function is
    used, or an exception will be thrown."""
    content_checksum = md5sum(contents)
    if not front.has_blob(content_checksum) and not front.new_snapshot_has_blob(content_checksum):
        front.init_new_blob(content_checksum, len(contents))
        front.add_blob_data(content_checksum, base64.b64encode(contents))
        front.blob_finished(content_checksum)
    now = int(time())
    front.add({'filename': filename,
               'md5sum': content_checksum,
               'ctime': now,
               'mtime': now,
               'size': len(contents)})

def set_file_contents(front, session_name, filename, contents):
    """Creates a new snapshot and replaces/creates the given file in
    the session."""
    if get_file_contents(front, session_name, filename) == contents:
        return # No changes necessary
    rev = front.find_last_revision(session_name)
    front.create_session(session_name, base_session = rev)
    add_file_simple(front, filename, contents)
    front.commit({'name': session_name, 
                  'date': ctime()})

valid_session_props = set(["ignore", "include"])

class Front:
    def __init__(self, repo):
        self.repo = repo
        self.new_session = None
        self.blobs_to_verify = []

    def get_repo_path(self):
        return self.repo.get_repo_path()

    def get_session_ids(self, session_name = None):
        sids = self.repo.get_all_sessions()
        if not session_name:
            return sids
        result = []
        for sid in sids:
            session_info = self.get_session_info(sid)
            name = session_info.get("name")
            if name == session_name:
                result.append(sid)
        return result

    def __set_session_property(self, session_name, property_name, new_value):
        assert property_name in valid_session_props
        meta_session_name = "__meta_" + session_name
        if self.find_last_revision(meta_session_name) == None:
            self.__mksession(meta_session_name)
        value_string = json.dumps(new_value, indent = 4)
        assert value_string == json.dumps(new_value, indent = 4), "Memory corruption?"
        set_file_contents(self, meta_session_name, property_name + ".json", value_string)

    def __get_session_property(self, session_name, property_name):
        """Returns the value of the given session property, or None if
        there is no such property."""
        assert property_name in valid_session_props
        meta_session_name = "__meta_" + session_name
        try:
            value_string = get_file_contents(self, meta_session_name, property_name + ".json")
        except SessionNotFoundError:
            return None
        if value_string == None:
            return None
        return json.loads(value_string)

    def set_session_ignore_list(self, session_name, new_list):
        assert isinstance(new_list, (tuple, list))
        self.__set_session_property(session_name, "ignore", new_list)
        
    def get_session_ignore_list(self, session_name):        
        value = self.__get_session_property(session_name, "ignore")
        if value == None:
            return []
        return value

    def set_session_include_list(self, session_name, new_list):
        assert isinstance(new_list, (tuple, list))
        self.__set_session_property(session_name, "include", new_list)
        
    def get_session_include_list(self, session_name):        
        value = self.__get_session_property(session_name, "include")
        if value == None:
            return []
        return value

    def get_session_info(self, id):
        """ Returns None if there is no such snapshot """
        if not self.repo.has_snapshot(id):
            return None
        session_reader = self.repo.get_session(id)
        properties = session_reader.get_properties()
        return properties['client_data']

    def get_session_fingerprint(self, id):
        session_reader = self.repo.get_session(id)        
        properties = session_reader.get_properties()
        assert "fingerprint" in properties
        return properties["fingerprint"]

    def get_session_bloblist(self, id):
        session_reader = self.repo.get_session(id)
        bloblist = list(session_reader.get_all_blob_infos())
        seen = set()
        for b in bloblist:
            assert b['filename'] not in seen, "Duplicate file found in bloblist - internal error"
            seen.add(b['filename'])
        return bloblist

    def create_session(self, session_name, base_session = None):
        """Creates a new snapshot for the given session."""
        assert isinstance(session_name, basestring), session_name
        assert not self.new_session, "There already exists an active new snapshot"
        self.new_session = self.repo.create_session(session_name = session_name, \
                                                        base_session = base_session)

    def cancel_snapshot(self):
        if not self.new_session:
            warn("Tried to cancel non-active new snapshot")
            return
        self.new_session.cancel()
        self.new_session = None

    def has_snapshot(self, session_name, snapshot_id):
        """ Returns True if there exists a session with the given
        session_name and snapshot id """
        if snapshot_id not in self.get_session_ids():
            return False
        session_info = self.get_session_info(snapshot_id)
        name = session_info.get("name", None)
        return name == session_name        

    def init_new_blob(self, blob_md5, size):
        self.new_session.init_new_blob(blob_md5, size)

    def add_blob_data(self, blob_md5, b64data):
        """ Must be called after a create_session()  """
        self.new_session.add_blob_data(blob_md5, base64.b64decode(b64data))

    def blob_finished(self, blob_md5):
        self.new_session.blob_finished(blob_md5)

    def add(self, metadata):
        """ Must be called after a create_session(). Adds a link to a existing
        blob. Will throw an exception if there is no such blob """
        assert metadata.has_key("md5sum")
        assert metadata.has_key("filename")
        self.new_session.add(metadata)

    def remove(self, filename):
        """ Remove the given file in the workdir from the current
        session. Requires that the current session has a base
        session""" 
        self.new_session.remove(filename)

    def mksession(self, sessionName):
        if sessionName.startswith("__"):
            raise UserError("Session names must not begin with double underscores.")
        if "/" in sessionName:
            raise UserError("Session names must not contain slashes.")
        if "\\" in sessionName:
            raise UserError("Session names must not contain backslashes.")
        return self.__mksession(sessionName)

    def __mksession(self, sessionName):
        if self.find_last_revision(sessionName) != None:
            raise Exception("There already exists a session named '%s'" % (session_name))
        self.create_session(session_name = sessionName)
        session_info = { "name": sessionName,
                         "timestamp": int(time()),
                         "date": ctime() }
        return self.commit(session_info)


    def commit(self, sessioninfo):
        assert self.new_session, "There is no active snapshot to commit"
        assert "name" in sessioninfo
        id = self.new_session.commit(sessioninfo)
        self.new_session = None
        return id

## Disabled until I can figure out how to make transparent 
##calls with binary data in jasonrpc
#    def get_blob(self, sum):
#        return self.repo.get_blob(sum)

    def get_blob_size(self, sum):
        return self.repo.get_blob_size(sum)

    def get_blob(self, sum, offset = 0, size = -1):
        datasource = self.repo.get_blob_reader(sum, offset, size)
        return datasource

    def has_blob(self, sum):
        return self.repo.has_blob(sum)

    def new_snapshot_has_blob(self, sum):
        assert self.new_session, "new_snapshot_has_blob() must only be called when a new snapshot is underway"
        return self.new_session.has_blob(sum)

    def find_last_revision(self, session_name):
        """ Returns the id of the latest snapshot in the specified
        session. Returns None if there is no such session. """
        return self.repo.find_last_revision(session_name)

    def init_verify_blobs(self):
        assert self.blobs_to_verify == []
        self.blobs_to_verify = self.repo.get_blob_names()
        for scanner in self.repo.scanners:
            scanner.scan_init()
        return len(self.blobs_to_verify)

    def verify_some_blobs(self):
        succeeded = []
        count = min(100, len(self.blobs_to_verify))
        for i in range(0, count):
            blob_to_verify = self.blobs_to_verify.pop()
            result = self.repo.verify_blob(blob_to_verify)
            assert result, "Blob failed verification:" + blob_to_verify
            succeeded.append(blob_to_verify)
        if not self.blobs_to_verify:
            for scanner in self.repo.scanners:
                scanner.scan_finish()
        return succeeded


class RevisionFront:
    """RevisionFront is a wrapper for the Front class that provides
    convenience methods to access some of the contents of a specific
    revision. 

    The bloblist_cache_fn is an optional callback that must accept an
    revision and return the bloblist for that revision (thus providing
    a clean way for client code to cache the bloblist). The resulting
    bloblist will be verified against session fingerprint. The
    function may return None, which is the same as not giving any
    cache function. That is, the full bloblist will be fetched from
    the repo. When a bloblist is loaded from the repo,
    save_bloblist_cache_fn() will be called with the revision and the
    bloblist as arguments."""

    def __init__(self, front, revision,
                 load_bloblist_cache_fn = None,
                 save_bloblist_cache_fn = None):
        assert type(revision) == int
        self.front = front
        self.revision = revision
        self.blobinfos = None
        self.load_bloblist_cache_fn = load_bloblist_cache_fn
        self.save_bloblist_cache_fn = save_bloblist_cache_fn

    def get_bloblist(self):
        if self.blobinfos == None:
            expected_fingerprint = self.front.get_session_fingerprint(self.revision)
            if self.load_bloblist_cache_fn:
                self.blobinfos = self.load_bloblist_cache_fn(self.revision)
                if self.blobinfos:
                    calc_fingerprint = bloblist_fingerprint(self.blobinfos)
                    assert calc_fingerprint == expected_fingerprint, \
                        "Cached bloblist did not match repo fingerprint"
            if self.blobinfos == None:
                self.blobinfos = self.front.get_session_bloblist(self.revision)
                self.bloblist_csums = set([b['md5sum'] for b in self.blobinfos])
                calc_fingerprint = bloblist_fingerprint(self.blobinfos)
                assert calc_fingerprint == expected_fingerprint, \
                    "Bloblist from repo did not match repo fingerprint? Repo corruption?"
                if self.save_bloblist_cache_fn:
                    self.save_bloblist_cache_fn(self.revision, self.blobinfos)
            self.bloblist_csums = set([b['md5sum'] for b in self.blobinfos])
        return self.blobinfos

    def exists_in_session(self, csum):
        """ Returns true if a file with the given checksum exists in this revision. """
        assert is_md5sum(csum)
        self.get_bloblist() # make sure self.bloblist_csums is loaded
        return csum in self.bloblist_csums

    def get_filesnames(self, csum):
        assert is_md5sum(csum)
        bloblist = self.get_bloblist()
        for b in bloblist:
            if b['md5sum'] == csum:
                yield b['filename']



class DryRunFront:

    def __init__(self, front):
        self.realfront = front

    def get_repo_path(self):
        return self.realfront.get_repo_path()

    def get_session_ids(self):
        return self.realfront.get_session_ids()

    def get_session_info(self, id):
        return self.realfront.get_session_properties(id)['client_data']

    def get_session_bloblist(self, id):
        return self.realfront.get_session_bloblist(id)

    def create_session(self, session_name, base_session = None):
        pass

    def init_new_blob(self, blob_md5, size):
        pass

    def add_blob_data(self, blob_md5, b64data):
        pass

    def blob_finished(self, blob_md5):
        pass

    def add(self, metadata):
        pass

    def remove(self, filename):
        pass

    def commit(self, sessioninfo = {}):
        return 0

    def get_blob_size(self, sum):
        return self.realfront.get_blob_size(sum)

    def get_blob_b64(self, sum, offset = 0, size = -1):
        return self.realfront.get_blob_b64(sum, offset, size)

    def has_blob(self, sum):
        return self.realfront.has_blob(sum)

    def new_snapshot_has_blob(self, sum):
        return False

    def find_last_revision(self, session_name):
        return self.realfront.find_last_revision(session_name)

    def mksession(self, sessionName):
        pass

for attrib in Front.__dict__:
    if not attrib.startswith("_") and callable(Front.__dict__[attrib]):
        if not attrib in DryRunFront.__dict__:
            pass
            #warn("Missing in DryRunFront: "+ attrib)
