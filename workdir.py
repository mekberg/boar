from __future__ import with_statement

import os
from front import Front
from blobrepo.repository import Repo
from common import *
from base64 import b64decode, b64encode
import settings
import time
import hashlib
import stat

if sys.version_info >= (2, 6):
    import json
else:
    import simplejson as json


class Workdir:
    def __init__(self, repoUrl, sessionName, offset, revision, root):
        assert os.path.isabs(root), "Workdir path must be absolute. Was: " + root
        self.repoUrl = repoUrl
        self.sessionName = sessionName
        self.offset = offset
        self.revision = revision
        self.root = root
        self.front = None
        self.md5cache = {}

        assert self.revision == None or self.revision > 0

    def write_metadata(self):
        workdir_path = self.root
        metadir = os.path.join(workdir_path, settings.metadir)        
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
        f = open("md5sum.txt", "w")
        for info in front.get_session_bloblist(self.revision):
            f.write(info['md5sum'] +" *" + info['filename'] + "\n")
        f.close()

    def checkout(self, write_meta = True):
        assert os.path.exists(self.root) and os.path.isdir(self.root)
        front = self.get_front()
        if not self.revision:
            self.revision = front.find_last_revision(self.sessionName)
        if write_meta:
            self.write_metadata()
        for info in front.get_session_bloblist(self.revision):
            if not info['filename'].startswith(self.offset):
                continue
            target = strip_path_offset(self.offset, info['filename'])
            target_path = os.path.join(self.root, target)
            fetch_blob(front, info['md5sum'], target_path)

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

        for sessionpath in new_files + modified_files:
            expected_md5sum = self.cached_md5sum(sessionpath)
            abspath = self.abspath(sessionpath)
            check_in_file(front, abspath, sessionpath, expected_md5sum)

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
        tree = get_tree(self.root, skip = [settings.metadir], absolute_paths = False)
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
        assert not os.path.isabs(relative_path), "Path must be relative to the workdir"
        if relative_path in self.md5cache:
            return self.md5cache[relative_path]
        csum = md5sum_file(self.abspath(relative_path))
        self.md5cache[relative_path] = csum
        return self.md5cache[relative_path]

    def abspath(self, path):
        """Transforms the given path from a session-relative path to a
        absolute path to the file in the current workdir. Takes path
        offsets into account. The given path must be a child of the
        current path offset, or an exception will be thrown."""
        without_offset = strip_path_offset(self.offset, path)
        return os.path.join(self.root, without_offset)

    def get_changes(self, skip_checksum = False):
        """ Compares the work dir with the checked out revision. Returns a
            tuple of four lists: unchanged files, new files, modified
            files, deleted files. By default, checksum is used to
            determine changed files. If skip_checksum is set to True,
            only file modification date is used to determine if a file
            has been changed. """
        assert not skip_checksum, "skip_checksum is not yet implemented"
        front = self.get_front()
        existing_files_list = get_tree(self.root, skip = [settings.metadir], absolute_paths = False)
        existing_files_list = map(lambda x: os.path.join(self.offset, x), existing_files_list)
        bloblist = []
        if self.revision != None:
            bloblist = front.get_session_bloblist(self.revision)
            bloblist = [i for i in bloblist if is_child_path(self.offset, i['filename'])]
        unchanged_files, new_files, modified_files, deleted_files, ignored_files = [], [], [], [], []
        for info in bloblist:
            fname = info['filename']
            if fname in existing_files_list:
                existing_files_list.remove(fname)
                if self.cached_md5sum(info['filename']) == info['md5sum']:
                    unchanged_files.append(fname)
                else:
                    modified_files.append(fname)
            if not os.path.exists(self.abspath(fname)):
                deleted_files.append(fname)
        for f in existing_files_list:
            if is_ignored(self.abspath(f)):
                print "Ignoring file", f
                existing_files_list.remove(f)
                ignored_files.append(f)
        new_files.extend(existing_files_list)

        if self.revision == None:
            assert not unchanged_files
            assert not modified_files
            assert not deleted_files
        result = unchanged_files, new_files, modified_files, deleted_files, ignored_files
        return result

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

def check_in_file(sessionwriter, abspath, sessionpath, expected_md5sum):
    """ Checks in the file found at the given "abspath" into the
    active "sessionwriter" with the path in the session given as
    "sessionpath". The md5sum of the file has to be provided. The
    checksum is compared to the file while it is read, to ensure it is
    consistent."""
    print "check_in_file(%s, %s, %s)" % (abspath, sessionpath, expected_md5sum)
    assert os.path.isabs(abspath), \
        "abspath must be absolute. Was: '%s'" % (path)
    assert os.path.exists(abspath), "Tried to check in file that does not exist: " + abspath
    blobinfo = create_blobinfo(abspath, sessionpath, expected_md5sum)
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

def fetch_blob(front, blobname, target_path):
    assert not os.path.exists(target_path)
    if not os.path.exists(os.path.dirname(target_path)):
        os.makedirs(os.path.dirname(target_path))
    size = front.get_blob_size(blobname)
    offset = 0
    f = open(target_path, "wb")
    while offset < size:
        data = b64decode(front.get_blob_b64(blobname, offset, 1000000))
        assert len(data) > 0
        offset += len(data)
        f.write(data)
    f.close()
