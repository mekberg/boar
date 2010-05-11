import os

from front import Front
from repository import Repo
from common import *
import settings

if sys.version_info >= (2, 6):
    import json
else:
    import simplejson as json


class Workdir:
    def __init__(self, repoUrl, sessionName, revision, root):
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
                out_list.append(os.path.join(dirname, name))
        all_files = []
        os.path.walk(self.root, visitor, all_files)
        remove_rootpath = lambda fn: my_relpath(fn, self.root)
        relative_paths = map(remove_rootpath, all_files)
        return relative_paths

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
        existing_files_list = self.get_tree()
        #print existing_files_list
        bloblist = front.get_session_bloblist(self.revision)
        unchanged_files, new_files, modified_files, deleted_files = [], [], [], []
        for info in bloblist:
            fname = info['filename']
            if fname in existing_files_list:
                existing_files_list.remove(fname)
                if self.cached_md5sum(info['filename']) == info['md5sum']:
                    unchanged_files.append(fname)
                else:
                    modified_files.append(fname)                    
            if not os.path.exists(fname):
                deleted_files.append(fname)
        new_files.extend(existing_files_list)

        remove_rootpath = lambda fn: my_relpath(fn, self.root)
        unchanged_files = map(remove_rootpath, unchanged_files)
        new_files = map(remove_rootpath, new_files)
        modified_files = map(remove_rootpath, modified_files)
        deleted_files = map(remove_rootpath, deleted_files)

        return unchanged_files, new_files, modified_files, deleted_files
