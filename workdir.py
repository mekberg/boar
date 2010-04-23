import os

from front import Front
from repository import Repo
from common import *
import settings

class Workdir:
    def __init__(self, repoUrl, sessionName, revision, root):
        self.repoUrl = repoUrl
        self.sessionName = sessionName
        self.revision = revision
        self.root = root
        self.front = None

    def get_front(self):
        if not self.front:
            self.front = Front(Repo(self.repoUrl))
        return self.front

    def get_changes(self, skip_checksum = False):
        """ Compares the work dir with the checked out revision. Returns a
            tuple of four lists: unchanged files, new files, modified
            files, deleted files. By default, checksum is used to
            determine changed files. If skip_checksum is set to True,
            only file modification date is used to determine if a file
            has been changed. """
        assert not skip_checksum, "skip_checksum is not yet implemented"
        front = self.get_front()
        def visitor(out_list, dirname, names):
            if settings.metadir in names:
                names.remove(settings.metadir)
            for name in names:
                name = unicode(name, encoding="utf_8")
                out_list.append(os.path.join(dirname, name))

        existing_files_list = []
        os.path.walk(self.root, visitor, existing_files_list)
        #print existing_files_list
        bloblist = front.get_session_bloblist(self.revision)
        unchanged_files, new_files, modified_files, deleted_files = [], [], [], []
        for info in bloblist:
            fname = os.path.join(self.root, info['filename'])
            if fname in existing_files_list:
                existing_files_list.remove(fname)
                if md5sum_file(fname) == info['md5sum']:
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
