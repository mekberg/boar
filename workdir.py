from __future__ import with_statement

import os
from front import Front
from blobrepo.repository import Repo
from common import *
from base64 import b64decode, b64encode
import bloblist
import settings
import time
import hashlib
import stat

if sys.version_info >= (2, 6):
    import json
else:
    import simplejson as json


class Workdir:
    def __init__(self, repoUrl, sessionName, revision, root):
        assert os.path.isabs(root), "Workdir path must be absolute. Was: " + root
        self.repoUrl = repoUrl
        self.sessionName = sessionName
        self.revision = revision
        self.root = root
        self.front = None
        self.md5cache = {}

    def write_metadata(self):
        workdir_path = self.root
        metadir = os.path.join(workdir_path, settings.metadir)        
        if not os.path.exists(metadir):
            os.mkdir(metadir)
        statusfile = os.path.join(workdir_path, settings.metadir, "info")
        with open(statusfile, "wb") as f:
            json.dump({'repo_path': self.repoUrl,
                       'session_name': self.sessionName,
                       'session_id': self.revision}, f, indent = 4)    
    def checkout(self, write_meta = True):
        assert os.path.exists(self.root) and os.path.isdir(self.root)
        front = self.get_front()
        if write_meta:
            self.write_metadata()
        for info in front.get_session_bloblist(self.revision):
            print info['filename']
            data = b64decode(front.get_blob_b64(info['md5sum']))
            assert data or info['size'] == 0
            filename = os.path.join(self.root, info['filename'])
            if not os.path.exists(os.path.dirname(filename)):
                os.makedirs(os.path.dirname(filename))
            with open(filename, "wb") as f:            
                f.write(data)

    def checkin(self, write_meta = True, force_primary_session = False, add_only = False):
        front = self.get_front()
        assert os.path.exists(self.root) and os.path.isdir(self.root)

        base_session = None
        if not force_primary_session:
            base_session = front.find_last_revision(self.sessionName)
        
        front.create_session(base_session)

        unchanged_files, new_files, modified_files, deleted_files, ignored_files = \
            self.get_changes()
        assert base_session or (not unchanged_files and not modified_files and not deleted_files)

        for f in new_files + modified_files:
            # A little hackish to store up the md5sums in one sweep
            # before starting to check them in. An attempt to reduce
            # the chance that the file is in disk cache when we read
            # it again for check-in later. (To avoid the problem that
            # a corrupted disk read is cached and not detected) TODO:
            # This is really a broken way to do it, and it should be
            # replaced with proper system-calls to read the file raw
            # from disk. But that's complicated.
            self.cached_md5sum(f)

        for f in new_files + modified_files:
            expected_md5sum = self.cached_md5sum(f)
            check_in_file(front, self.root, os.path.join(self.root, f), expected_md5sum)

        if not add_only:
            for f in deleted_files:
                front.remove(f)

        session_info = {}
        session_info["name"] = self.sessionName
        session_info["timestamp"] = int(time.time())
        session_info["date"] = time.ctime()
        self.revision = front.commit(session_info)
        if write_meta:
            self.write_metadata()
        return self.revision

    def get_front(self):
        if not self.front:
            self.front = Front(Repo(self.repoUrl))
        return self.front

    def exists_in_session(self, csum):
        """ Returns true if a file with the given checksum exists in the
            current session. """
        blobinfos = self.get_front().get_session_bloblist(self.revision)
        for info in blobinfos:
            if info['md5sum'] == csum:
                return True
        return False

    def exists_in_workdir(self, csum):
        """ Returns true if at least one file with the given checksum exists
            in the workdir. """
        tree = self.get_tree()
        for f in tree:
            if self.cached_md5sum(f) == csum:
                return True
        return False

    def get_blobinfo(self, relpath):
        """ Returns the info dictionary for the given path and the current
            session. The given file does not need to exist, the information is
            fetched from the repository"""
        blobinfos = self.get_front().get_session_bloblist(self.revision)
        for info in blobinfos:
            if info['filename'] == relpath:
                return info
        return None

    def cached_md5sum(self, relative_path):
        if relative_path in self.md5cache:
            return self.md5cache[relative_path]
        csum = md5sum_file(os.path.join(self.root, relative_path))
        self.md5cache[relative_path] = csum
        return self.md5cache[relative_path]

    def get_tree(self):
        """ Returns a simple list of all the files and directories in the
            workdir (except meta directories). """
        def visitor(out_list, dirname, names):
            if settings.metadir in names:
                names.remove(settings.metadir)
            for name in names:
                name = unicode(name, encoding="utf_8")
                fullpath = os.path.join(dirname, name)
                if not os.path.isdir(fullpath):
                    out_list.append(fullpath)
        all_files = []
        #print "Walking", self.root
        os.path.walk(self.root, visitor, all_files)
        return all_files

    def rel_to_abs(self, relpath):
        return os.path.join(self.root, relpath)

    def get_changes(self, skip_checksum = False):
        """ Compares the work dir with the checked out revision. Returns a
            tuple of four lists: unchanged files, new files, modified
            files, deleted files. By default, checksum is used to
            determine changed files. If skip_checksum is set to True,
            only file modification date is used to determine if a file
            has been changed. """
        assert not skip_checksum, "skip_checksum is not yet implemented"
        front = self.get_front()
        remove_rootpath = lambda fn: convert_win_path_to_unix(my_relpath(fn, self.root))
        # existing_files_list is root-relative
        existing_files_list = map(remove_rootpath, self.get_tree())
        bloblist = []
        if self.revision != None:
            bloblist = front.get_session_bloblist(self.revision)
        unchanged_files, new_files, modified_files, deleted_files, ignored_files = [], [], [], [], []
        for info in bloblist:
            fname = info['filename']
            if fname in existing_files_list:
                existing_files_list.remove(fname)
                if self.cached_md5sum(info['filename']) == info['md5sum']:
                    unchanged_files.append(fname)
                else:
                    modified_files.append(fname)
            if not os.path.exists(os.path.join(self.root, fname)):
                deleted_files.append(fname)
        for f in existing_files_list:
            if is_ignored(os.path.join(self.root, f)):
                print "Ignoring file", f
                existing_files_list.remove(f)
                ignored_files.append(f)
        new_files.extend(existing_files_list)

        if self.revision == None:
            assert not unchanged_files
            assert not modified_files
            assert not deleted_files
        return unchanged_files, new_files, modified_files, deleted_files, ignored_files

def is_ignored(dirname, entryname = None):
    if entryname == None:
        entryname = os.path.basename(dirname)
        dirname = os.path.dirname(dirname)
    full_path = os.path.join(dirname, entryname)
    assert os.path.exists(full_path), "Path '%s' does not exist " % (full_path)
    if settings.metadir == entryname:
        return True
    if os.path.isdir(full_path):
        return False
    elif not os.path.isfile(full_path):
        return True
    elif os.path.islink(full_path):
        return True
    return False

def check_in_file(sessionwriter, root, path, expected_md5sum):
    """ Checks in the file found at the given "path" into the active
    "sessionwriter". The actual filename checked in is determined by
    subtracting the "root" from the path. The md5sum of the file has
    to be provided. The checksum is compared to the file while it is
    read, to ensure it is consistent."""

    assert os.path.isabs(path), \
        "path must be absolute here. Was: '%s'" % (path)
    blobinfo = create_blobinfo(path, root, expected_md5sum)
    if not sessionwriter.has_blob(expected_md5sum):
        with open_raw(path) as f:
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
    wd = Workdir(repoUrl=info['repo_path'], 
                 sessionName=info['session_name'], 
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

def init_repo_from_meta(path):
    front = None
    msg = None
    meta = find_meta(path)
    if meta:
        pass # print "Found meta data at", meta
    else:
        print "No workdir found at", path
        return None

    info = load_meta_info(meta)
    repo_path = info['repo_path']
    session_name = info['session_name']
    session_id = info['session_id']

    # print "Using repo at", repo_path, "with session", session_name
    front = Front(Repo(repo_path))
    return front

def create_blobinfo(path, root, md5sum):
    assert is_md5sum(md5sum)
    st = os.lstat(path)
    blobinfo = {}
    blobinfo["filename"] = convert_win_path_to_unix(my_relpath(path, root))
    blobinfo["md5sum"] = md5sum
    blobinfo["ctime"] = st[stat.ST_CTIME]
    blobinfo["mtime"] = st[stat.ST_MTIME]
    blobinfo["size"] = st[stat.ST_SIZE]
    return blobinfo

