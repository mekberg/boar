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
from front import Front, DryRunFront, RevisionFront
from blobrepo.repository import Repo
from treecomp import TreeComparer
from common import *
from boar_exceptions import *
from boar_common import *
import client

from base64 import b64decode, b64encode
import time
import hashlib
import stat
import copy
import cPickle
import tempfile
import fnmatch
import sqlite3
import atexit

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

VERSION_FILE = "wd_version.txt"
CURRENT_VERSION = 2
METADIR = ".boar"
CCACHE_FILE = "ccache.db"

class Workdir:
    def __init__(self, repoUrl, sessionName, offset, revision, root):
        assert repoUrl == None or isinstance(repoUrl, unicode)
        assert isinstance(sessionName, unicode)
        assert isinstance(offset, unicode)
        assert revision == None or isinstance(revision, int)
        assert isinstance(root, unicode)
        assert os.path.isabs(root), "Workdir path must be absolute. Was: " + root
        assert os.path.exists(root)
        self.repoUrl = repoUrl
        self.sessionName = sessionName
        self.offset = offset
        self.revision = revision
        self.root = root
        self.metadir = os.path.join(self.root, METADIR)
        self.front = None

        self.__upgrade()

        if self.repoUrl:
            self.front = self.get_front()

        self.sqlcache = None
        if os.path.exists(self.metadir):
            self.sqlcache = ChecksumCache(self.metadir + "/" + CCACHE_FILE)
        else:
            self.sqlcache = ChecksumCache(":memory:")

        assert self.revision == None or self.revision > 0
        self.revision_fronts = {}
        self.tree_csums = None
        self.tree = None
        self.output = FakeFile()

    def __upgrade(self):
        v0_metadir = os.path.join(self.root, ".meta")
        if os.path.exists(v0_metadir):
            os.rename(v0_metadir, self.metadir)
        if not os.path.exists(self.metadir):
            return
        version = self.__get_workdir_version()
        if version > 2:
            raise UserError("This workdir is created by a future version of boar.")
        if version == 0 or version == 1:
            notice("Upgrading file checksum cache - rescan necessary, next operation will take longer than usual.")
            if os.path.exists(self.metadir + "/" + 'md5sumcache'):
                safe_delete_file(self.metadir + "/" + 'md5sumcache')
            if os.path.exists(self.metadir + "/" + CCACHE_FILE):
                safe_delete_file(self.metadir + "/" + CCACHE_FILE)
            self.__set_workdir_version(2)

    def __reload_tree(self):
        self.tree = get_tree(self.root, skip = [METADIR], absolute_paths = False)
        self.tree_csums == None

    def __get_workdir_version(self):
        version_file = os.path.join(self.metadir, VERSION_FILE)
        if os.path.exists(version_file):
            return int(read_file(version_file))
        return 0

    def __set_workdir_version(self, new_version):
        assert type(new_version) == int
        version_file = os.path.join(self.metadir, VERSION_FILE)
        replace_file(version_file, str(new_version))

    def setLogOutput(self, fout):
        self.output = fout

    def write_metadata(self):
        workdir_path = self.root
        metadir = self.metadir
        if not os.path.exists(metadir):
            os.mkdir(metadir)
        statusfile = os.path.join(workdir_path, METADIR, "info")
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
            self.__set_workdir_version(CURRENT_VERSION)
        for info in front.get_session_bloblist(self.revision):
            if not is_child_path(self.offset, info['filename']):
                continue
            target = strip_path_offset(self.offset, info['filename'])
            target_path = os.path.join(self.root, target)
            fetch_blob(front, info['md5sum'], target_path, overwrite = False)

    def update_revision(self, new_revision = None):
        assert new_revision == None or isinstance(new_revision, int)
        front = self.get_front()
        if new_revision:
            if not front.has_snapshot(self.sessionName, new_revision):
                raise UserError("No such session or snapshot: %s@%s" % (self.sessionName, new_revision))
        else:
            new_revision = front.find_last_revision(self.sessionName)
        self.revision = new_revision
        self.write_metadata()

    def update(self, new_revision = None, log = None, ignore_errors = False):
        assert self.revision, "Cannot update. Current revision is unknown: '%s'" % self.revision
        if not log:
            # Don't do this as a default argument, as sys.stdout may
            # have been redirected (see issue 18)
            log = StreamEncoder(sys.stdout)
        unchanged_files, new_files, modified_files, deleted_files, ignored_files = \
            self.get_changes(self.revision)
        front = self.get_front()
        if new_revision:
            if not front.has_snapshot(self.sessionName, new_revision):
                raise UserError("No such session or snapshot: %s@%s" % (self.sessionName, new_revision))
        else:
            new_revision = front.find_last_revision(self.sessionName)
        old_bloblist = self.get_bloblist(self.revision)
        new_bloblist = front.get_session_bloblist(new_revision)
        new_bloblist_dict = bloblist_to_dict(new_bloblist)
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
        self.tree = None
        self.write_metadata()

    def checkin(self, write_meta = True, force_primary_session = False, \
                    fail_on_modifications = False, add_only = False, dry_run = False, \
                    log_message = None, ignore_errors = False):
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
            self.get_changes(self.revision, ignore_errors = ignore_errors)
        assert base_snapshot or (not unchanged_files and not modified_files and not deleted_files)

        if fail_on_modifications and modified_files:
            raise UserError("This import would replace some existing files")

        if add_only:
            deleted_files = ()
            modified_files = ()

        self.__create_snapshot(new_files + modified_files, deleted_files, base_snapshot, front, log_message, ignore_errors)

        if write_meta:
            self.write_metadata()
        return self.revision

    def __create_snapshot(self, files, deleted_files, base_snapshot, front, log_message, ignore_errors):
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
            abspath = self.abspath(sessionpath)
            expected_md5sum = self.cached_md5sum(wd_path)
            try:
                check_in_file(front, abspath, sessionpath, expected_md5sum, log = self.output)
            except EnvironmentError, e:
                if ignore_errors:
                    warn("Ignoring unreadable file: %s" % abspath)
                else:
                    front.cancel_snapshot()
                    raise UserError("Unreadable file: %s" % abspath)

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
        return self.revision


    def get_front(self):
        if self.front:
            return self.front
        self.front = create_front(self.repoUrl)
        return self.front

    def get_revision_front(self, revision):
        front = self.get_front()
        if revision not in self.revision_fronts:
             # Only save the latest used revision. A trivial MRU cache.
            self.revision_fronts.clear()
            self.revision_fronts[revision] = RevisionFront(front, revision, 
                                                           self.__load_cached_bloblist, 
                                                           self.__save_cached_bloblist)
        return self.revision_fronts[revision]

    def __load_cached_bloblist(self, revision):
        assert type(revision) == int and revision > 0
        bloblist_file = os.path.join(self.metadir, "bloblistcache"+str(revision)+".bin")
        if os.path.exists(bloblist_file):
            try:
                return cPickle.load(safe_open(bloblist_file, "rb"))
            except: 
                warn("Exception while accessing bloblist cache - ignoring")
                return None
        return None

    def __save_cached_bloblist(self, revision, bloblist):
        assert type(revision) == int and revision > 0
        bloblist_file = os.path.join(self.metadir, "bloblistcache"+str(revision)+".bin")
        if os.path.exists(self.metadir):
            cPickle.dump(bloblist, open(bloblist_file, "wb"))        

    def get_bloblist(self, revision):
        assert type(revision) == int, "Revision was '%s'" % revision
        return self.get_revision_front(revision).get_bloblist()

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
        for info in self.get_bloblist(self.revision):
            if info['filename'] == relpath:
                return info
        return None

    def cached_md5sum(self, relative_path):
        """Return the md5 checksum of the given file as hex encoded
        string."""
        assert not os.path.isabs(relative_path), "Path must be relative to the workdir. Was: "+relative_path
        assert self.sqlcache
        abspath = self.wd_abspath(relative_path)
        stat = os.stat(abspath)
        sums = self.sqlcache.get(relative_path, stat.st_mtime)
        recent_change = abs(time.time() - stat.st_mtime) < 5.0
        if sums and not recent_change:
            return sums
        md5, = checksum_file(abspath, ("md5",))
        self.sqlcache.set(relative_path, stat.st_mtime, md5)
        assert is_md5sum(md5)
        return md5

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

    def get_changes(self, revision = None, ignore_errors = False):
        """ Compares the work dir with given revision, or the latest
            revision if no revision is given. Returns a tuple of five
            lists: unchanged files, new files, modified files, deleted
            files, ignored files."""
        front = self.get_front()
        self.__reload_tree()
        existing_files_list = copy.copy(self.tree)
        prefix = ""
        if self.offset:
            prefix = self.offset + "/"
        filelist = {}
        for fn in existing_files_list:
            f = prefix + fn
            assert not is_windows_path(f), "Was:" + f
            assert not os.path.isabs(f)
            try:
                filelist[f] = self.cached_md5sum(fn)
            except EnvironmentError, e:
                if ignore_errors:
                    warn("Ignoring unreadable file: %s" % f)
                else:
                    raise UserError("Unreadable file: %s" % f)
        
        if revision != None:
            bloblist = self.get_bloblist(revision)
        else:
            if self.revision == None:
                assert self.sessionName
                self.revision = front.find_last_revision(self.sessionName)
                if not self.revision:
                    raise UserError("No session found named '%s'" % (self.sessionName))
            bloblist = self.get_bloblist(self.revision)

        bloblist_dict = {}
        for i in bloblist:
            if is_child_path(self.offset, i['filename']):
                bloblist_dict[i['filename']] = i['md5sum']

        comp = TreeComparer(bloblist_dict, filelist)
        unchanged_files, new_files, modified_files, deleted_files = comp.as_tuple()

        ignore_patterns = front.get_session_ignore_list(self.sessionName)
        include_patterns = front.get_session_include_list(self.sessionName)
        ignored_files = ()
        if include_patterns: # optimization
            ignored_files += tuple([fn for fn in new_files if not fnmatch_multi(include_patterns, fn)])
            ignored_files += tuple([fn for fn in modified_files if not fnmatch_multi(include_patterns, fn)])
        if ignore_patterns: # optimization
            ignored_files += tuple([fn for fn in new_files if fnmatch_multi(ignore_patterns, fn)])
            ignored_files += tuple([fn for fn in modified_files if fnmatch_multi(ignore_patterns, fn)])
        if ignored_files:
            new_files = tuple([fn for fn in new_files if fn not in ignored_files])
            modified_files = tuple([fn for fn in modified_files if fn not in ignored_files])


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

def check_in_file(front, abspath, sessionpath, expected_md5sum, log = FakeFile()):
    """ Checks in the file found at the given "abspath" into the
    active "front" with the path in the session given as
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
    if not front.has_blob(expected_md5sum) and not front.new_snapshot_has_blob(expected_md5sum):
        # File does not exist in repo or previously in this new snapshot. Upload it.
        with open_raw(abspath) as f:
            m = hashlib.md5()
            freader = file_reader(f, blocksize = 1048576) # 1048576 = 2^20
            for block in freader:
                m.update(block)
                front.add_blob_data(expected_md5sum, b64encode(block))
            front.add_blob_data(expected_md5sum, b64encode(""))
            assert m.hexdigest() == expected_md5sum, \
                "File changed during checkin process: " + path
    front.add(blobinfo)

def init_workdir(path):
    """ Tries to find a workdir root directory at the given path or
    above. Returns a workdir object if successful, or None if not. """
    metapath = find_meta(tounicode(os.getcwd()))
    info = load_meta_info(metapath)
    root = os.path.split(metapath)[0]
    wd = Workdir(repoUrl=info['repo_path'], 
                 sessionName=info['session_name'], 
                 offset=info.get("offset", ""), 
                 revision=info['session_id'],
                 root=root) 
    return wd


def find_meta(path):
    meta = os.path.join(path, METADIR)
    if os.path.exists(meta):
        return meta
    meta_v0 = os.path.join(path, ".meta")
    if os.path.exists(meta_v0):
        return meta_v0
    head, tail = os.path.split(path)
    if head == path:
        return None
    return find_meta(head)

def load_meta_info(metapath):
    with safe_open(os.path.join(metapath, "info"), "rb") as f:
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
    
    
class ChecksumCache:
    def __init__(self, dbpath):
        # Use a proxy to avoid circular reference to the repo,
        # allowing this object to be garbed at shutdown and triggering
        # the __del__ function.
        assert dbpath == ":memory:" or os.path.isabs(dbpath)
        assert dbpath == ":memory:" or os.path.exists(os.path.dirname(dbpath))
        self.dbpath = dbpath
        self.conn = None
        self.__init_db()
        atexit.register(self.sync)
        self.rate_limiter = RateLimiter(1.0)

    def __init_db(self):
        if self.conn:
            return
        try:
            self.conn = sqlite3.connect(self.dbpath, check_same_thread = False)
            self.conn.execute("CREATE TABLE IF NOT EXISTS ccache (path text, mtime unsigned int, md5 char(32), row_md5 char(32))")
            self.conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ccache_index ON ccache (path, mtime)")
            self.conn.commit()
        except sqlite3.DatabaseError, e:
            raise

    def set(self, path, mtime, md5):
        assert type(path) == unicode
        md5_row = md5sum(path.encode("utf8") + "!" + str(mtime) + "!" + md5)
        try:
            self.conn.execute("REPLACE INTO ccache (path, mtime, md5, row_md5) VALUES (?, ?, ?, ?)", (path, mtime, md5, md5_row))
            if self.rate_limiter.ready():
                self.sync()
        except sqlite3.DatabaseError, e:
            raise

    def get(self, path, mtime):
        assert type(path) == unicode
        try:
            c = self.conn.cursor()
            c.execute("SELECT md5, row_md5 FROM ccache WHERE path = ? AND mtime = ?", (path, mtime))
            rows = c.fetchall()
        except sqlite3.DatabaseError, e:
            raise
        if not rows:
            return None
        assert len(rows) == 1
        md5, row_md5 = rows[0]
        expected_md5_row = md5sum(path.encode("utf8") + "!" + str(mtime) + "!" + md5.encode("utf8"))
        if row_md5 != expected_md5_row:
            raise
        return md5

    def sync(self):
        if self.conn:
            self.conn.commit()

