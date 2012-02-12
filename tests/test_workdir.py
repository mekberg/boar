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
import sys, os, unittest, tempfile, shutil
from copy import copy
import socket, errno
import base64

DATA1 = "tjosan"
DATA1_MD5 = "5558e0551622725a5fa380caffa94c5d"
DATA2 = "tjosan hejsan"
DATA2_MD5 = "923574a1a36aebc7e1f586b7d363005e"

TMPDIR=tempfile.gettempdir()

""" 
note: to execute a single test, do something like:
python tests/test_workdir.py TestWorkdir.testGetChangesMissingFile
"""

if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import workdir
from blobrepo import repository
from common import get_tree, my_relpath, convert_win_path_to_unix, md5sum
from boar_exceptions import UserError
import server
from front import Front

class DevNull:
    def write(self, s):
        pass

boar_dirs = [".boar", ".boar_session"]

def read_tree(path, skiplist = []):
    """Returns a mapping {filename: content, ...} for the given directory
    tree"""
    assert os.path.exists(path)
    def visitor(out_map, dirname, names):
        encoding = sys.getfilesystemencoding()
        dirname = dirname.decode(encoding)
        for skip in skiplist:
            if skip in names:
                names.remove(skip)
        for name in names:
            name = name.decode(encoding)
            fullpath = os.path.join(dirname, name)
            assert fullpath.startswith(path+os.path.sep), fullpath
            relpath = convert_win_path_to_unix(fullpath[len(path)+1:])
            if not os.path.isdir(fullpath):
                out_map[relpath] = open(fullpath).read()
    result = {}
    os.path.walk(path, visitor, result)
    return result

def write_tree(path, filemap, create_root = True):
    """Accepts a mapping {filename: content, ...} and writes it to the
    tree starting at the given """
    if create_root:
        os.mkdir(path)
    else:
        assert os.path.exists(path)
    for filename in filemap.keys():
        assert not os.path.exists(filename)
        assert not os.path.isabs(filename)
        fullpath = os.path.join(path, filename)
        dirpath = os.path.dirname(fullpath)
        try:
            os.makedirs(dirpath)
        except:
            pass
        with open(fullpath, "wb") as f:
            f.write(filemap[filename])

class WorkdirHelper:
    def mkdir(self, path):
        assert not os.path.isabs(path)
        dirpath = os.path.join(self.workdir, path)
        os.makedirs(dirpath)

    def addWorkdirFile(self, path, content):
        assert not os.path.isabs(path)
        filepath = os.path.join(self.workdir, path)
        with open(filepath, "w") as f:
            f.write(content)
    
    def rmWorkdirFile(self, path):
        assert not os.path.isabs(path)
        filepath = os.path.join(self.workdir, path)
        os.unlink(filepath)

    def createTmpName(self, suffix = ""):
        filename = tempfile.mktemp(prefix='testworkdir'+suffix+"_", dir=TMPDIR)
        filename = filename.decode()
        self.remove_at_teardown.append(filename)
        return filename

    def assertContents(self, path, expected_contents):
        with open(path, "rb") as f:
            file_contents = f.read()
            self.assertEquals(file_contents, expected_contents)

    
    #session_id = wd.checkin(write_meta = options.create_workdir, 
    #                        add_only = True, dry_run = options.dry_run)
        

class TestFront(unittest.TestCase, WorkdirHelper):
    def setUp(self):
        self.remove_at_teardown = []
        self.workdir = self.createTmpName()
        self.repopath = self.createTmpName()
        repository.create_repository(self.repopath)
        os.mkdir(self.workdir)
        self.wd = workdir.Workdir(self.repopath, u"TestSession", u"", None, self.workdir)
        self.wd.setLogOutput(DevNull())
        self.wd.use_progress_printer(False)
        self.front = self.wd.front
        id = self.wd.get_front().mksession(u"TestSession")
        assert id == 1
        
    def testGetIgnoreDefault(self):
        got_list = self.front.get_session_ignore_list(u"TestSession")
        self.assertEquals(got_list, [])

    def testSetAndGetIgnore(self):
        ignore_list = ["ignore1", "ignore2"]
        self.front.set_session_ignore_list(u"TestSession", copy(ignore_list))
        got_list = self.front.get_session_ignore_list(u"TestSession")
        self.assertEquals(ignore_list, got_list)

    def testSetAndGetIgnoreRepeated(self):
        self.front.set_session_ignore_list(u"TestSession", ["ignore1"])
        self.front.set_session_ignore_list(u"TestSession", ["ignore2"])
        got_list = self.front.get_session_ignore_list(u"TestSession")
        self.assertEquals(got_list, ["ignore2"])

    def testSetIgnoreErrorDetect(self):
        self.assertRaises(AssertionError, self.front.set_session_ignore_list, 
                          u"TestSession", "string must not be accepted")
        self.assertRaises(AssertionError, self.front.set_session_ignore_list, 
                          u"TestSession", 19) # no numbers allowed
        self.assertRaises(AssertionError, self.front.set_session_ignore_list, 
                          u"TestSession", None) # None not allowed

    def tearDown(self):
        for d in self.remove_at_teardown:
            shutil.rmtree(d, ignore_errors = True)

class TestWorkdir(unittest.TestCase, WorkdirHelper):
    def setUp(self):
        self.remove_at_teardown = []
        self.workdir = self.createTmpName()
        self.repopath = self.createTmpName()
        self.repoUrl = self.repopath
        repository.create_repository(self.repopath)
        os.mkdir(self.workdir)
        self.wd = workdir.Workdir(self.repopath, u"TestSession", u"", None, self.workdir)
        self.wd.setLogOutput(DevNull())
        self.wd.use_progress_printer(False)
        id = self.wd.get_front().mksession(u"TestSession")
        assert id == 1

    def createWorkdir(self, repoUrl, tree = {}, offset = u"", revision = None):
        wdroot = self.createTmpName()
        write_tree(wdroot, tree)
        wd = workdir.Workdir(repoUrl, u"TestSession", offset, revision, wdroot)
        wd.setLogOutput(DevNull())
        wd.use_progress_printer(False)
        self.assertTrue(wd.get_front().find_last_revision(u"TestSession"))
        return wd

    def tearDown(self):
        for d in self.remove_at_teardown:
            shutil.rmtree(d, ignore_errors = True)

    #
    # Actual tests start here
    #

    def testEmpty(self):
        changes = self.wd.get_changes()
        self.assertEqual(changes, ((), (), (), (), ()))

    def testGetChangesUnversionedFile(self):
        # Test unversioned file
        self.addWorkdirFile("tjosan.txt", "tjosanhejsan")
        changes = self.wd.get_changes()
        self.assertEqual(changes, ((), ("tjosan.txt",), (), (), ()))

    def testGetChangesUnchangedFile(self):        
        self.addWorkdirFile("tjosan.txt", "tjosanhejsan")
        self.wd.checkin()
        changes = self.wd.get_changes()
        self.assertEqual(changes, (("tjosan.txt",), (), (), (), ()))

    def testGetChangesUnchangedFileWithFunkyName(self):        
        name = u"Tjosan_räk smörgås.txt"
        self.addWorkdirFile(name, "tjosanhejsan")
        self.wd.checkin()
        changes = self.wd.get_changes()
        self.assertEqual(changes, ((name,), (), (), (), ()))

    def testGetChangesMissingFile(self):
        self.addWorkdirFile("tjosan.txt", "tjosanhejsan")
        self.wd.checkin()
        self.rmWorkdirFile("tjosan.txt")
        changes = self.wd.get_changes()
        self.assertEqual(changes, ((), (), (), ("tjosan.txt",), ()))

    def testGetChangesUnchangedFileSubdir(self):
        self.mkdir("subdir")
        self.addWorkdirFile("subdir/tjosan.txt", "tjosanhejsan")
        self.wd.checkin()
        changes = self.wd.get_changes()
        self.assertEqual(changes, (("subdir/tjosan.txt",), (), (), (), ()))

    def testTwoNewIdenticalFiles(self):
        self.mkdir("subdir")
        self.addWorkdirFile("subdir/tjosan1.txt", "tjosanhejsan")
        self.addWorkdirFile("subdir/tjosan2.txt", "tjosanhejsan")
        self.wd.checkin()
        changes = self.wd.get_changes()
        # Order doesnt matter below really, so this is fragile
        self.assertEqual(changes, (tuple(["subdir/tjosan2.txt", "subdir/tjosan1.txt"]), (), (), (), ()))

    def testWriteAndReadTree(self):
        """ Really only test helper functions write_tree() and
        read_tree() themselves"""
        tree = {"tjosan.txt": "tjosan content",
                "subdir/nisse.txt": "nisse content"}
        testdir = self.createTmpName()
        write_tree(testdir, tree)
        tree2 = read_tree(testdir)
        self.assertEqual(tree, tree2)

    def testOffsetCheckout(self):
        tree1 = {'file.txt': 'fc1',
                 'subdir1/subdirfile1.txt': 'fc2'}
        wd = self.createWorkdir(self.repoUrl, tree1)
        wd.checkin()
        wd = self.createWorkdir(self.repoUrl, offset = u"subdir1")
        wd.checkout()
        subtree = read_tree(wd.root, skiplist = boar_dirs)
        self.assertEqual(subtree, {'subdirfile1.txt': 'fc2'})

    def testOffsetCheckin(self):
        tree1 = {'file.txt': 'fc1',
                 'subdir1/subdirfile1.txt': 'fc2'}
        wd = self.createWorkdir(self.repoUrl, tree1)
        wd.checkin()
        wd = self.createWorkdir(self.repoUrl, offset = u"subdir1")
        wd.checkout()
        subtree = read_tree(wd.root, skiplist = boar_dirs)
        write_tree(wd.root, {'newfile.txt': 'nf'}, create_root = False)
        wd.checkin()
        wd = self.createWorkdir(self.repoUrl, offset = u"subdir1")
        wd.checkout()
        subtree = read_tree(wd.root, skiplist = boar_dirs)
        self.assertEqual(subtree, {'subdirfile1.txt': 'fc2',
                                   'newfile.txt': 'nf'})        

    def testAddOnlyCommit(self):
        """ Add-only commits should ignore modifications and
        deletions, and only commit new files, if any. """
        tree1 = {'modified.txt': 'mod1',
                 'deleted.txt': 'del'}
        wd = self.createWorkdir(self.repoUrl, tree1)
        wd.checkin()
        tree2 = {'modified.txt': 'mod2',
                 'new.txt': 'new'}
        wd = self.createWorkdir(self.repoUrl, tree2)
        wd.checkin(add_only = True)
        wd = self.createWorkdir(self.repoUrl)
        wd.checkout()
        newtree = read_tree(wd.root, skiplist = boar_dirs)
        self.assertEqual(newtree, {'modified.txt': 'mod1',
                                   'deleted.txt': 'del',
                                   'new.txt': 'new'})
        
    def testOverwriteImport(self):
        tree1 = {'file.txt': 'file.txt contents'}
        tree2 = {'file.txt': 'file.txt other contents'}
        wd = self.createWorkdir(self.repoUrl, tree1)
        wd.checkin()
        wd = self.createWorkdir(self.repoUrl, tree2)
        self.assertRaises(UserError, wd.checkin, fail_on_modifications = True)

    def testImportDryRun(self):
        """ Test that nothing is changed by a dry run commit """
        wd = self.createWorkdir(self.repoUrl, {"file1.txt": "fc1", # modified
                                               "file2.txt": "fc2"}) # deleted
        wd.checkin()
        wd = self.createWorkdir(self.repoUrl, {"file1.txt": "fc1 mod", # modified
                                               'file3.txt': 'fc3'}) # new
        id = wd.checkin(dry_run = True)
        self.assertEquals(id, 0)
        wd = self.createWorkdir(self.repoUrl)
        wd.checkout()
        newtree = read_tree(wd.root, skiplist = boar_dirs)
        self.assertEquals(newtree, {'file1.txt': 'fc1',
                                    'file2.txt': 'fc2'})

    def testUpdate(self):
        wd = self.createWorkdir(self.repoUrl, 
                                {'file2.txt': 'f2'})
        rev1 = wd.checkin()
        wd = self.createWorkdir(self.repoUrl,
                                {'file2.txt': 'f2 mod2', # modified file
                                 'file3.txt': 'f3'}) # new file
        rev2 = wd.checkin()
        wd_update = self.createWorkdir(self.repoUrl, 
                                       {'file2.txt': 'f2 mod1'}, 
                                       revision = rev1)
        wd_update.update()
        updated_tree = read_tree(wd_update.root, skiplist = boar_dirs)
        self.assertEquals(updated_tree, {'file2.txt': 'f2 mod1',
                                         'file3.txt': 'f3'})

    def testUpdateResume(self):
        """ Test the case that some parts of the workdir are already
        up to date (like after an aborted update)."""
        wd = self.createWorkdir(self.repoUrl, 
                                {'file1.txt': 'f1 v1',
                                 'file2.txt': 'f2 v1',
                                 'file3.txt': 'f3 v1'})
        rev1 = wd.checkin()
        wd = self.createWorkdir(self.repoUrl,
                                {'file1.txt': 'f1 v2',
                                 'file2.txt': 'f2 v2',
                                 'file3.txt': 'f3 v2'})
        rev2 = wd.checkin()
        wd_update = self.createWorkdir(self.repoUrl, 
                                       {'file1.txt': 'f1 v2',  # unexpected v2
                                        'file2.txt': 'f2 v1',  # normal v1
                                        'file3.txt': 'f3 mod'},# normal modification, but not v2
                                       revision = rev1)
        wd_update.update()
        updated_tree = read_tree(wd_update.root, skiplist = boar_dirs)
        self.assertEquals(updated_tree, {'file1.txt': 'f1 v2',
                                         'file2.txt': 'f2 v2',
                                         'file3.txt': 'f3 mod'})

    def testUpdateWithOffset(self):
        wd = self.createWorkdir(self.repoUrl, 
                                {'subdir/d/file2.txt': 'f2'})
        rev1 = wd.checkin()
        wd = self.createWorkdir(self.repoUrl,
                                {'subdir/d/file2.txt': 'f2 mod2', # modified file
                                 'subdir/d/file3.txt': 'f3'}) # new file
        rev2 = wd.checkin()
        wd_update = self.createWorkdir(self.repoUrl, 
                                       {'d/file2.txt': 'f2 mod1'}, 
                                       revision = rev1,
                                       offset = u"subdir")
        wd_update.update()
        updated_tree = read_tree(wd_update.root, skiplist = boar_dirs)
        self.assertEquals(updated_tree, {'d/file2.txt': 'f2 mod1',
                                         'd/file3.txt': 'f3'})

    def testUpdateDeletion(self):
        """ Only file3.txt should be deleted by the update, since it
        is unchanged. The other two should remain untouched."""
        wd = self.createWorkdir(self.repoUrl, 
                                {'file1.txt': 'f1', 
                                 'file2.txt': 'f2', 
                                 'file3.txt': 'f3'})
        rev1 = wd.checkin()
        wd = self.createWorkdir(self.repoUrl, {})
        rev2 = wd.checkin()
        wd_update = self.createWorkdir(self.repoUrl, 
                                       {'file1.txt': 'f1 mod',
                                        'file2.txt': 'f2 mod',
                                        'file3.txt': 'f3'}, 
                                       revision = rev1)
        wd_update.update()
        updated_tree = read_tree(wd_update.root, skiplist = boar_dirs)
        self.assertEquals(updated_tree, {'file1.txt': 'f1 mod',
                                         'file2.txt': 'f2 mod'})

    def testUpdateDeletionWithOffset(self):
        """ Only file3.txt should be deleted by the update, since it
        is unchanged. The other two should remain untouched."""
        wd = self.createWorkdir(self.repoUrl, 
                                {'subdir/d/file1.txt': 'f1', 
                                 'subdir/d/file2.txt': 'f2', 
                                 'subdir/d/file3.txt': 'f3'})
        rev1 = wd.checkin()
        wd = self.createWorkdir(self.repoUrl, {})
        rev2 = wd.checkin()
        wd_update = self.createWorkdir(self.repoUrl, 
                                       {'d/file1.txt': 'f1 mod',
                                        'd/file2.txt': 'f2 mod',
                                        'd/file3.txt': 'f3'}, 
                                       revision = rev1,
                                       offset = u"subdir")
        wd_update.update()
        updated_tree = read_tree(wd_update.root, skiplist = boar_dirs)
        self.assertEquals(updated_tree, {'d/file1.txt': 'f1 mod',
                                         'd/file2.txt': 'f2 mod'})

    def testEmptyFile(self):
        tree = {'file.txt': ''}
        wd = self.createWorkdir(self.repoUrl, tree)
        wd.checkin()
        wd = self.createWorkdir(self.repoUrl)
        wd.checkout()
        co_tree = read_tree(wd.root, skiplist = boar_dirs)
        self.assertEquals(tree, co_tree)

    def testIgnore(self):
        tree = {'file.txt': 'f1',
                'file.ignore': 'f2'}
        wd = self.createWorkdir(self.repoUrl, tree)
        wd.front.set_session_ignore_list(u"TestSession", ["*.ignore"])
        wd.checkout()
        wd.checkin()

        wd = self.createWorkdir(self.repoUrl)
        wd.checkout()
        co_tree = read_tree(wd.root, skiplist = boar_dirs)
        self.assertEquals({'file.txt': 'f1'}, co_tree)

    def testInclude(self):
        tree = {'file.txt': 'f1',
                'file.ignore': 'f2'}
        wd = self.createWorkdir(self.repoUrl, tree)
        wd.front.set_session_include_list(u"TestSession", ["*.txt"])
        wd.checkout()
        wd.checkin()

        wd = self.createWorkdir(self.repoUrl)
        wd.checkout()
        co_tree = read_tree(wd.root, skiplist = boar_dirs)
        self.assertEquals({'file.txt': 'f1'}, co_tree)

    def testIgnoreInclude(self):
        tree = {'file.txt': 'f1',
                'file.ignore': 'f2'}
        wd = self.createWorkdir(self.repoUrl, tree)
        wd.front.set_session_include_list(u"TestSession", ["file.*"])
        wd.front.set_session_ignore_list(u"TestSession", ["*.ignore"])
        wd.checkout()
        wd.checkin()

        wd = self.createWorkdir(self.repoUrl)
        wd.checkout()
        co_tree = read_tree(wd.root, skiplist = boar_dirs)
        self.assertEquals({'file.txt': 'f1'}, co_tree)


    def testIgnoreStickyness(self):
        tree = {'file.txt': 'f1',
                'file.ignore': 'f2'}
        wd = self.createWorkdir(self.repoUrl, tree)
        wd.front.set_session_ignore_list(u"TestSession", ["*.ignore"])
        wd.checkout()
        wd.checkin()
        id = wd.checkin()
        # Need to change this test if we make non-changing commits become NOPs.
        self.assertEquals(id, 5) 
        wd = self.createWorkdir(self.repoUrl)
        wd.checkout()
        co_tree = read_tree(wd.root, skiplist = boar_dirs)
        self.assertEquals({'file.txt': 'f1'}, co_tree)

    def testIgnoreModifications(self):
        """Expected behavior is that modifications of previously
        committed (but now ignored) files should be ignored. But they
        should still be checked out if they exist."""
        tree = {'file.txt': 'f1',
                'file.ignore': 'f2',
                'file-modified.ignore': 'f3'}
        wd = self.createWorkdir(self.repoUrl, tree)
        wd.checkin()

        wd.front.set_session_ignore_list(u"TestSession", ["*.ignore"])
        wd.update()
        write_tree(wd.root, {'file-modified.ignore': 'f3 mod'}, False)
        wd.checkin()

        wd = self.createWorkdir(self.repoUrl)
        wd.checkout()
        co_tree = read_tree(wd.root, skiplist = boar_dirs)
        self.assertEquals(tree, co_tree)

    def testFastModifications(self):
        """Verify that the checksum cache is not confused by more than
        one change per second"""
        wd = self.createWorkdir(self.repoUrl)
        wd.checkin()
        for n in range(0, 10):
            write_tree(wd.root, {'file.txt': 'content 1'}, False)
            self.assertEqual(wd.cached_md5sum(u"file.txt"), "9297ab3fbd56b42f6566284119238125")
            write_tree(wd.root, {'file.txt': 'content 2'}, False)        
            self.assertEqual(wd.cached_md5sum(u"file.txt"), "6685cd62b95f2c58818cb20e7292168b")

    def testIncludeModifications(self):
        """Expected behavior is that modifications of previously
        committed (but now ignored) files should be ignored. But they
        should still be checked out if they exist."""
        tree = {'file.txt': 'f1',
                'file.ignore': 'f2',
                'file-modified.ignore': 'f3'}
        wd = self.createWorkdir(self.repoUrl, tree)
        wd.checkin()

        wd.front.set_session_include_list(u"TestSession", ["*.txt"])
        wd.update()
        write_tree(wd.root, {'file-modified.ignore': 'f3 mod'}, False)
        wd.checkin()

        wd = self.createWorkdir(self.repoUrl)
        wd.checkout()
        co_tree = read_tree(wd.root, skiplist = boar_dirs)
        self.assertEquals(tree, co_tree)

    def testExpectedMetaFilesUpdate(self):
        tree = {'file.txt': 'f1'}
        wd = self.createWorkdir(self.repoUrl, tree)
        wd.checkin()
        wd.front.set_session_ignore_list(u"TestSession", ["*.ignore"])
        wd.update()
        wd.get_changes()
        full_tree_filenames = set(read_tree(wd.root).keys())
        expected_filenames = set([u'file.txt', 
                                  u'.boar/info', 
                                  u'.boar/bloblistcache2.bin'])

        self.assertEquals(expected_filenames, full_tree_filenames)

    def testExistingFileTwice(self):
        """Test derived sha256 checksum. It is only returned from the
        derived storage at the third checkin (at the first, it is
        never requested since there is no file with that md5 in the
        repo. At the second, it is generated and returned. At the
        third, it is not generated, only loaded from storage."""
        wd = self.createWorkdir(self.repoUrl, 
                                {'file1.txt': "data"})
        wd.checkin()
        write_tree(wd.root, {'subdir/file2.txt': "data"}, False)
        wd.checkin()
        write_tree(wd.root, {'subdir/file3.txt': "data"}, False)
        wd.checkin()
                   
                              

class TestWorkdirWithServer(TestWorkdir):
    def create_server(self):
        for p in range(11000, 12000):
            try:
                self.server = server.ThreadedBoarServer(self.raw_repopath, p)
                self.port = p
                break
            except socket.error, e:
                if e.errno != errno.EADDRINUSE:
                    raise e

    def setUp(self):
        self.remove_at_teardown = []
        self.workdir = self.createTmpName()
        self.raw_repopath = self.createTmpName()
        repository.create_repository(self.raw_repopath)
        os.mkdir(self.workdir)
        self.create_server()
        self.server.serve()
        self.repoUrl = u"boar://localhost:%s/" % (self.port)
        self.wd = workdir.Workdir(self.repoUrl, u"TestSession", u"", 
                                  None, self.workdir)
        self.wd.setLogOutput(DevNull())
        self.wd.use_progress_printer(False)
        front = self.wd.get_front()
        assert front.isRemote
        id = self.wd.get_front().mksession(u"TestSession")
        assert id == 1

class TestPartialCheckin(unittest.TestCase, WorkdirHelper):
    def setUp(self):
        self.remove_at_teardown = []
        self.workdir = self.createTmpName("_wd")
        self.repopath = self.createTmpName("_repo")
        repository.create_repository(self.repopath)

    def createTestRepo(self):
        os.mkdir(self.workdir)
        wd = workdir.Workdir(self.repopath, u"TestSession", u"", None, self.workdir)
        wd.setLogOutput(DevNull())
        wd.use_progress_printer(False)
        self.addWorkdirFile("onlyintopdir.txt", "nothing")
        self.mkdir("mysubdir")
        self.addWorkdirFile("mysubdir/insubdir.txt", "nothing2")
        id = wd.get_front().mksession(u"TestSession")
        assert id == 1
        id = wd.checkin()
        assert id == 2
        shutil.rmtree(self.workdir, ignore_errors = True)

    def tearDown(self):
        for d in self.remove_at_teardown:
            shutil.rmtree(d, ignore_errors = True)

    def testPartialCheckout(self):
        self.createTestRepo()
        os.mkdir(self.workdir)
        wd = workdir.Workdir(self.repopath, u"TestSession", u"mysubdir", None, self.workdir)
        wd.setLogOutput(DevNull())
        wd.use_progress_printer(False)
        wd.checkout()
        tree = get_tree(wd.root, absolute_paths = False)
        #tree = wd.get_tree(absolute_paths = True)
        self.assertEquals(set(tree), set(["insubdir.txt", '.boar/info', '.boar/wd_version.txt']))

if __name__ == '__main__':
    unittest.main()

