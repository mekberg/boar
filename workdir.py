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
from front import Front, DryRunFront
from blobrepo.sessions import bloblist_fingerprint
from blobrepo.repository import Repo
from treecomp import TreeComparer
from common import *
from boar_exceptions import *
import client

from base64 import b64decode, b64encode
import settings
import time
import hashlib
import stat
import copy
import cPickle
import anydbm
import tempfile
import fnmatch
# shelve and dbhash are only imported as a workaround for py2exe,
# which otherwise for some reason will forget to include a dbm implementation
import shelve
import dbhash

if sys.version_info >= (2, 6):
    import json
else:
    import simplejson as json

class FakeFile:
    def write(self, s):
        pass


class Workdir:
    def __init__(self, repoUrl, sessionName, offset, revision, root):
        assert isinstance(root, unicode)
        assert os.path.isabs(root), "Workdir path must be absolute. Was: " + root
        assert os.path.exists(root)
        self.repoUrl = repoUrl
        self.sessionName = sessionName
        self.offset = offset
        self.revision = revision
        self.root = root
        self.metadir = os.path.join(self.root, settings.metadir)
        self.front = None
        if self.repoUrl:
            self.front = self.get_front()
        if os.path.exists(self.metadir):
            self.md5cache = anydbm.open(self.metadir + "/" + 'md5sumcache', 'c')
        else:
            self.md5cache = {}
        assert self.revision == None or self.revision > 0

        self.blobinfos = None
        self.bloblist_csums = None
        self.tree_csums = None
        self.tree = None
        self.output = FakeFile()

    def __reload_tree(self):
        self.tree = get_tree(self.root, skip = [settings.metadir], absolute_paths = False)
        self.tree_csums == None

    def setLogOutput(self, fout):
        self.output = fout

    def write_metadata(self):
        workdir_path = self.root
        metadir = self.metadir
        if not os.path.exists(metadir):
            os.mkdir(metadir)
        statusfile = os.path.join(workdir_path, settings.metadir, "info")
        with open(statusfile, "wb") as f:
            json.dump({'repo_path': self.repoUrl,
                       'session_name': self.sessionName,
                       'offset': self.offset,
                       'session_id': self.revision}, f, indent = 4)

    def export_md5(self):
        assert not os.path.exists("md5sum.txt")
        front = self.get_front()
        with StreamEncoder(open("md5sum.txt", "w"), errors = "strict") as f:
            for info in front.get_session_bloblist(self.revision):
                f.write(info['md5sum'] +" *" + info['filename'] + "\n")

    def checkout(self, write_meta = True):
        assert os.path.exists(self.root) and os.path.isdir(self.root)
        front = self.get_front()
        if not self.revision:
            self.revision = front.find_last_revision(self.sessionName)
        if write_meta:
            self.write_metadata()
        for info in front.get_session_bloblist(self.revision):
            if not is_child_path(self.offset, info['filename']):
                continue
            target = strip_path_offset(self.offset, info['filename'])
            target_path = os.path.join(self.root, target)
            fetch_blob(front, info['md5sum'], target_path, overwrite = False)

    def update(self, new_revision = None, log = None, ignore_errors = False):
        assert self.revision, "Cannot update. Current revision is unknown: '%s'" % self.revision
        if not log:
            # Don't do this as a default argument, as sys.stdout may
            # have been redirected (see issue 18)
            log = StreamEncoder(sys.stdout)
        unchanged_files, new_files, modified_files, deleted_files, ignored_files = \
            self.get_changes()
        front = self.get_front()
        if new_revision:
            if not front.has_snapshot(self.sessionName, new_revision):
                raise UserError("No such session or snapshot: %s@%s" % (self.sessionName, new_revision))
        else:
            new_revision = front.find_last_revision(self.sessionName)
        new_bloblist = front.get_session_bloblist(new_revision)
        new_bloblist_dict = bloblist_to_dict(new_bloblist)
        old_bloblist = self.get_bloblist()
        for b in new_bloblist:
            if not is_child_path(self.offset, b['filename']):
                continue
            if b['filename'] in modified_files:
                print >>log, "Skipping update of modified file", b['filename']
                continue
            target_wdpath = strip_path_offset(self.offset, b['filename'])
            target_abspath = os.path.join(self.root, target_wdpath)
            if not os.path.exists(target_abspath) or self.cached_md5sum(target_wdpath) != b['md5sum']:
                print >>log, "Updating:", b['filename']
                try:
                    fetch_blob(front, b['md5sum'], target_abspath, overwrite = True)
                except (IOError, OSError), e:
                    print >>log, "Could not update file %s: %s" % (b['filename'], e.strerror)
                    if not ignore_errors:
                        raise UserError("Errors during update - update aborted")
        for b in old_bloblist:
            if not is_child_path(self.offset, b['filename']):
                continue
            if b['filename'] not in new_bloblist_dict:
                if b['filename'] in modified_files:
                    print >>log, "Skipping deletion of modified file", b['filename']
                    continue
                try:
                    os.remove(self.abspath(b['filename']))
                    print >>log, "Deleted:", b['filename']
                except:
                    print >>log, "Deletion failed:", b['filename']
        self.revision = new_revision
        self.blobinfos = None
        self.bloblist_csums = None
        self.tree = None
        self.write_metadata()
        print >>log, "Workdir now at revision", self.revision

    def checkin(self, write_meta = True, force_primary_session = False, \
                    fail_on_modifications = False, add_only = False, dry_run = False, \
                    log_message = None):
        front = self.get_front()
        if dry_run:
            front = DryRunFront(front)
        assert os.path.exists(self.root) and os.path.isdir(self.root)

        latest_rev = front.find_last_revision(self.sessionName)
        if self.revision != None and latest_rev != self.revision:
            assert latest_rev > self.revision, \
                "Workdir revision %s is later than latest repository revision %s?" % (self.revision, latest_rev)
            raise UserError("Workdir is not up to date. Please perform an update first.")
        base_snapshot = None
        if not force_primary_session:
            base_snapshot = front.find_last_revision(self.sessionName)
        
        unchanged_files, new_files, modified_files, deleted_files, ignored_files = \
            self.get_changes()
        assert base_snapshot or (not unchanged_files and not modified_files and not deleted_files)

        if fail_on_modifications and modified_files:
            raise UserError("This import would replace some existing files")

        if add_only:
            deleted_files = ()
            modified_files = ()

        self.__create_snapshot(new_files + modified_files, deleted_files, base_snapshot, front, log_message)

        if write_meta:
            self.write_metadata()
        return self.revision

    def __create_snapshot(self, files, deleted_files, base_snapshot, front, log_message):
        """ Creates a new snapshot of the files in this
        workdir. Modified and new files are passed in the 'files'
        argument, deleted files in the 'deleted_files' argument. The
        new snapshot will be created as a modification of the snapshot
        given in the 'base_snapshot' argument."""

        for f in files:
            # A little hackish to store up the md5sums in one sweep
            # before starting to check them in. An attempt to reduce
            # the chance that the file is in disk cache when we read
            # it again for check-in later. (To avoid the problem that
            # a corrupted disk read is cached and not detected) TODO:
            # This is really a broken way to do it, and it should be
            # replaced with proper system-calls to read the file raw
            # from disk. But that's complicated.
            self.cached_md5sum(strip_path_offset(self.offset, f))

        try:
            front.create_session(session_name = self.sessionName, base_session = base_snapshot)
        except FileMutex.MutexLocked, e:
            raise UserError("The session '%s' is in use (lockfile %s)" % (self.sessionName, e.mutex_file))

        for sessionpath in files:
            wd_path = strip_path_offset(self.offset, sessionpath)
            expected_md5sum = self.cached_md5sum(wd_path)
            abspath = self.abspath(sessionpath)
            check_in_file(front, abspath, sessionpath, expected_md5sum, log = self.output)

        for f in deleted_files:
            front.remove(f)

        session_info = {}
        session_info["name"] = self.sessionName
        session_info["timestamp"] = int(time.time())
        session_info["date"] = time.ctime()
        if log_message != None:
            assert type(log_message) == unicode, "Log message must be in unicode"
            session_info["log_message"] = log_message
        self.revision = front.commit(session_info)
        self.blobinfos = None # Force reload of blobinfos
        return self.revision


    def get_front(self):
        if self.front:
            return self.front
        self.front = create_front(self.repoUrl)
        return self.front

    def exists_in_session(self, csum):
        """ Returns true if a file with the given checksum exists in the
            current session. """
        assert is_md5sum(csum)
        self.get_bloblist() # ensure self.bloblist_csums is initialized
        return csum in self.bloblist_csums

    def get_filesnames(self, csum):
        assert is_md5sum(csum)
        bloblist = self.get_bloblist()
        for b in bloblist:
            if b['md5sum'] == csum:
                yield b['filename']

    def __load_bloblist(self):
        if not self.revision:
            front = self.get_front()
            self.revision = front.find_last_revision(self.sessionName)
        if not self.revision:
            raise UserError("There is no session named '%s'" % (self.sessionName))
        bloblist_file = os.path.join(self.metadir, "bloblistcache"+str(self.revision)+".bin")
        if os.path.exists(bloblist_file):
            self.blobinfos = cPickle.load(open(bloblist_file, "rb"))
        else:
            self.blobinfos = self.get_front().get_session_bloblist(self.revision)
            if os.path.exists(self.metadir):
                cPickle.dump(self.blobinfos, open(bloblist_file, "wb"))
        self.bloblist_csums = set([b['md5sum'] for b in self.blobinfos])
        expected_fingerprint = self.get_front().get_session_fingerprint(self.revision)
        calc_fingerprint = bloblist_fingerprint(self.blobinfos)
        assert calc_fingerprint == expected_fingerprint, \
            "Cached bloblist did not match repo bloblist"

    def get_bloblist(self):
        if self.blobinfos == None:
            self.__load_bloblist()
        return self.blobinfos

    def exists_in_workdir(self, csum):
        """ Returns true if at least one file with the given checksum exists
            in the workdir. """
        if self.tree == None:
            self.__reload_tree()
        if self.tree_csums == None:
            self.tree_csums = set()
            for f in self.tree:
                self.tree_csums.add(self.cached_md5sum(f))
        return csum in self.tree_csums

    def get_blobinfo(self, relpath):
        """ Returns the info dictionary for the given path and the current
            session. The given file does not need to exist, the information is
            fetched from the repository"""
        for info in self.get_bloblist():
            if info['filename'] == relpath:
                return info
        return None

    def cached_md5sum(self, relative_path):
        assert not os.path.isabs(relative_path), "Path must be relative to the workdir. Was: "+relative_path
        abspath = self.wd_abspath(relative_path)
        stat = os.stat(abspath)
        key = relative_path.encode("utf-8") + "!" + str(int(stat.st_mtime))
        if key in self.md5cache:
            return self.md5cache[key]
        csum = md5sum_file(abspath)
        self.md5cache[key] = csum
        return self.md5cache[key]

    def wd_abspath(self, wd_path):
        """Transforms the given workdir path into a system absolute
        path"""
        assert not is_windows_path(wd_path)
        assert not os.path.isabs(wd_path)
        result = self.root + "/" + wd_path
        return result

    def abspath(self, session_path):
        """Transforms the given path from a session-relative path to a
        absolute path to the file in the current workdir. Takes path
        offsets into account. The given path must be a child of the
        current path offset, or an exception will be thrown."""
        assert not is_windows_path(session_path)
        without_offset = strip_path_offset(self.offset, session_path)
        result = self.root + "/" + without_offset
        return result

    def get_changes(self):
        """ Compares the work dir with the checked out
            revision. Returns a tuple of five lists: unchanged files,
            new files, modified files, deleted files, ignored
            files. """
        front = self.get_front()
        self.__reload_tree()
        existing_files_list = copy.copy(self.tree)
        prefix = ""
        if self.offset:
            prefix = self.offset + "/"
        filelist = {}
        for fn in existing_files_list:
            f = prefix + fn
            filelist[f] = self.cached_md5sum(fn)
            assert not is_windows_path(f), "Was:" + f
            assert not os.path.isabs(f)
        
        bloblist = {}
        if self.revision == None:
            assert self.sessionName
            self.revision = front.find_last_revision(self.sessionName)
            if not self.revision:
                raise UserError("No session found named '%s'" % (self.sessionName))

        for i in self.get_bloblist():
            if is_child_path(self.offset, i['filename']):
                bloblist[i['filename']] = i['md5sum']

        comp = TreeComparer(bloblist, filelist)
        unchanged_files, new_files, modified_files, deleted_files = comp.as_tuple()

        ignore_patterns = front.get_session_ignore_list(self.sessionName)
        include_patterns = front.get_session_include_list(self.sessionName)
        ignored_files = ()
        if include_patterns: # optimization
            ignored_files = tuple([fn for fn in new_files if not fnmatch_multi(include_patterns, fn)])
            new_files = tuple([fn for fn in new_files if fn not in ignored_files])
        if ignore_patterns: # optimization
            ignored_files += tuple([fn for fn in new_files if fnmatch_multi(ignore_patterns, fn)])
            new_files = tuple([fn for fn in new_files if fn not in ignored_files])

        if self.revision == None:
            assert not unchanged_files
            assert not modified_files
            assert not deleted_files, deleted_files
        result = unchanged_files, new_files, modified_files, deleted_files, ignored_files
        return result

def fnmatch_multi(patterns, filename):
    for pattern in patterns:
        if fnmatch.fnmatch(filename, pattern):
            return True
    return False

def check_in_file(sessionwriter, abspath, sessionpath, expected_md5sum, log = FakeFile()):
    """ Checks in the file found at the given "abspath" into the
    active "sessionwriter" with the path in the session given as
    "sessionpath". The md5sum of the file has to be provided. The
    checksum is compared to the file while it is read, to ensure it is
    consistent."""
    assert os.path.isabs(abspath), \
        "abspath must be absolute. Was: '%s'" % (path)
    assert ".." not in sessionpath.split("/"), \
           "'..' not allowed in paths or filenames. Was: " + sessionpath
    assert "\\" not in sessionpath, "Was: '%s'" % (path)
    assert os.path.exists(abspath), "Tried to check in file that does not exist: " + abspath
    blobinfo = create_blobinfo(abspath, sessionpath, expected_md5sum)
    log.write("Checking in %s => %s\n" % (abspath, sessionpath))
    if not sessionwriter.has_blob(expected_md5sum):
        with open_raw(abspath) as f:
            m = hashlib.md5()
            while True:
                data = f.read(1048576) # 1048576 = 2^20
                m.update(data)
                sessionwriter.add_blob_data(expected_md5sum, b64encode(data))
                if data == "":
                    assert m.hexdigest() == expected_md5sum, \
                        "File changed during checkin process: " + path
                    break
    sessionwriter.add(blobinfo)

def init_workdir(path):
    """ Tries to find a workdir root directory at the given path or
    above. Returns a workdir object if successful, or None if not. """
    front = init_repo_from_meta(path)
    if not front:
        return None
    metapath = find_meta(os.getcwd())
    info = load_meta_info(metapath)
    root = os.path.split(metapath)[0]
    root = root.decode()
    wd = Workdir(repoUrl=info['repo_path'], 
                 sessionName=info['session_name'], 
                 offset=info.get("offset", ""), 
                 revision=info['session_id'],
                 root=root) 
    return wd


def find_meta(path):
    meta = os.path.join(path, settings.metadir)
    if os.path.exists(meta):
        return meta
    head, tail = os.path.split(path)
    if head == path:
        return None
    return find_meta(head)

def load_meta_info(metapath):
    with open(os.path.join(metapath, "info"), "rb") as f:
        info = json.load(f)
    return info

def create_front(repoUrl):
    if repoUrl.startswith("boar://"):
        front = client.connect(repoUrl)
        front.isRemote = True
    else:
        front = Front(Repo(repoUrl))
        front.isRemote = False
    return front

def init_repo_from_meta(path):
    front = None
    msg = None
    meta = find_meta(path)
    if not meta:
        raise UserError("No workdir found at %s" % path)

    info = load_meta_info(meta)
    repo_path = info['repo_path']
    session_name = info['session_name']
    session_id = info['session_id']
    front = create_front(repo_path)
    return front

def create_blobinfo(abspath, sessionpath, md5sum):
    assert is_md5sum(md5sum)
    assert sessionpath == convert_win_path_to_unix(sessionpath), \
        "Session path not valid: " + sessionpath
    st = os.lstat(abspath)
    blobinfo = {}
    blobinfo["filename"] = sessionpath
    blobinfo["md5sum"] = md5sum
    blobinfo["ctime"] = st[stat.ST_CTIME]
    blobinfo["mtime"] = st[stat.ST_MTIME]
    blobinfo["size"] = st[stat.ST_SIZE]
    return blobinfo

def fetch_blob(front, blobname, target_path, overwrite = False):
    assert overwrite or not os.path.exists(target_path)
    target_dir = os.path.dirname(target_path)
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
    size = front.get_blob_size(blobname)
    offset = 0
    datareader = front.get_blob(blobname)
    assert datareader
    if overwrite and os.path.exists(target_path):
        # TODO: some kind of garbage bin instead of deletion
        os.remove(target_path)
    tmpfile_fd, tmpfile = tempfile.mkstemp(dir = target_dir)
    try:
        with os.fdopen(tmpfile_fd, "wb") as f:
            while datareader.bytes_left() > 0:
                f.write(datareader.read(2**14))
        os.rename(tmpfile, target_path)
    finally:
        if os.path.exists(tmpfile):
            os.remove(tmpfile)

def bloblist_to_dict(bloblist):
    d = {}
    for b in bloblist:
        d[b['filename']] = b
    assert(len(d) == len(bloblist)), \
        "All filenames must be unique in the revision"
    return d
    
    
    
