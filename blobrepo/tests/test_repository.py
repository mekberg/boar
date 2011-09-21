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

import sys, os, unittest, tempfile, shutil
from copy import copy

DATA1 = "tjosan"
DATA1_MD5 = "5558e0551622725a5fa380caffa94c5d"
DATA2 = "tjosan hejsan"
DATA2_MD5 = "923574a1a36aebc7e1f586b7d363005e"

DATA3 = "tjosan hejsan tjosan hejsan hejsan"
DATA3_MD5 = "cafa2ed1e085869b3bfe9e43b60e7a5a"

TMPDIR=tempfile.gettempdir()

SESSION_NAME = u"RepoTestSession"

if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from blobrepo import repository
from common import tounicode

class TestBlobRepo(unittest.TestCase):
    def setUp(self):
        self.repopath = tounicode(tempfile.mktemp(dir=TMPDIR))
        repository.create_repository(self.repopath)
        self.repo = repository.Repo(self.repopath)
        self.sessioninfo1 = {"foo": "bar",
                             "name": SESSION_NAME}
        self.fileinfo1 = {"filename": u"testfilename.txt",
                          "md5sum": DATA1_MD5}
        self.fileinfo2 = {"filename": "testfilename2.txt",
                          "md5sum": DATA2_MD5}
        self.fileinfo3 = {"filename": "testfilename3.txt",
                          "md5sum": DATA3_MD5}

    def tearDown(self):
        #shutil.rmtree(self.repopath, ignore_errors = True)
        pass

    def assertListsEqualAsSets(self, lst1, lst2):
        self.assertEqual(len(lst1), len(lst2))
        for i in lst1:
            self.assert_(i in lst2)
        for i in lst2:
            self.assert_(i in lst1)

    def test_empty_commit(self):
        writer = self.repo.create_session(SESSION_NAME)
        id = writer.commit()        
        self.assertEqual(1, id, "Session ids starts from 1") 
        self.assertEqual(self.repo.get_all_sessions(), [1], 
                         "There should be exactly one session")

    def test_double_commit(self):
        writer = self.repo.create_session(SESSION_NAME)
        writer.commit()        
        self.assertRaises(Exception, writer.commit)        
        
    def test_session_info(self):
        committed_info = copy(self.sessioninfo1)
        writer = self.repo.create_session(SESSION_NAME)
        id = writer.commit(committed_info)
        self.assertEqual(committed_info, self.sessioninfo1,
                         "Given info dict was changed during commit")
        reader = self.repo.get_session(id)
        self.assertEqual(self.sessioninfo1, reader.get_properties()['client_data'],
                         "Read info differs from committed info")

    def test_simple_blob(self):
        committed_info = copy(self.fileinfo1)
        writer = self.repo.create_session(SESSION_NAME)
        writer.add_blob_data(DATA1_MD5, DATA1)
        writer.add(committed_info)
        self.assertEqual(committed_info, self.fileinfo1)
        id = writer.commit()
        reader = self.repo.get_session(id)
        blobinfos = list(reader.get_all_blob_infos())
        self.assertEqual(blobinfos, [self.fileinfo1])

    def test_secondary_session(self):
        writer1 = self.repo.create_session(SESSION_NAME)
        writer1.add_blob_data(DATA1_MD5, DATA1)
        writer1.add(self.fileinfo1)
        id1 = writer1.commit()
        writer2 = self.repo.create_session(SESSION_NAME, base_session = id1)
        writer2.add_blob_data(DATA2_MD5, DATA2)
        writer2.add(self.fileinfo2)
        id2 = writer2.commit()
        reader = self.repo.get_session(id2)
        blobinfos = list(reader.get_all_blob_infos())
        self.assertListsEqualAsSets(blobinfos, [self.fileinfo1, self.fileinfo2])

    def test_remove(self):
        writer1 = self.repo.create_session(SESSION_NAME)
        writer1.add_blob_data(DATA1_MD5, DATA1)
        writer1.add(self.fileinfo1)
        id1 = writer1.commit()
        writer2 = self.repo.create_session(SESSION_NAME, base_session = id1)
        writer2.remove(self.fileinfo1['filename'])
        id2 = writer2.commit()
        blobinfos = list(self.repo.get_session(id1).get_all_blob_infos())
        self.assertEqual(blobinfos, [self.fileinfo1])
        blobinfos = list(self.repo.get_session(id2).get_all_blob_infos())
        self.assertEqual(blobinfos, [])

    def test_remove_nonexisting(self):
        writer1 = self.repo.create_session(SESSION_NAME)
        self.assertRaises(Exception, writer1.remove, "doesnotexist.txt")        

    def test_split(self):
        #  0          1        2         3
        #  0123456789012345678901234567890123456789
        # "tjosan hejsan tjosan hejsan hejsan"
        # cafa2ed1e085869b3bfe9e43b60e7a5a
        writer = self.repo.create_session(SESSION_NAME)
        writer.add_blob_data(DATA3_MD5, DATA3)
        writer.add(self.fileinfo3)
        writer.commit()
        writer = self.repo.create_session(SESSION_NAME)
        writer.split_blob("cafa2ed1e085869b3bfe9e43b60e7a5a", [14,28])
        split_snapshot = writer.commit()
        redundant = list(self.repo.find_redundant_raw_blobs())
        self.assertEquals(redundant, ["cafa2ed1e085869b3bfe9e43b60e7a5a"])
        os.remove(self.repo.get_blob_path("cafa2ed1e085869b3bfe9e43b60e7a5a"))
        reader = self.repo.get_session(split_snapshot)
        blobinfos = reader.get_all_blob_infos()
        for bi in blobinfos:
            self.assertTrue(self.repo.verify_blob(bi['md5sum']))

    def testSha256(self):
        writer = self.repo.create_session(SESSION_NAME)
        writer.add_blob_data(DATA3_MD5, DATA3)
        writer.add(self.fileinfo3)
        writer.commit()
        sha256 = self.repo.sha256.get_sha256(DATA3_MD5)
        self.assertEquals(sha256, "c61711eee86561d24bba9b541f2c3621a39f0e80e36a6407abfb68bc51264c10")

    def testSha256CacheCorruption(self):
        expected_sha256 = "c61711eee86561d24bba9b541f2c3621a39f0e80e36a6407abfb68bc51264c10"
        writer = self.repo.create_session(SESSION_NAME)
        writer.add_blob_data(DATA3_MD5, DATA3)
        writer.add(self.fileinfo3)
        writer.commit()
        sha256 = self.repo.sha256.get_sha256(DATA3_MD5)
        self.assertEquals(sha256, expected_sha256)
        self.repo.close()
        dbname = os.path.join(self.repopath, "derived/sha256/sha256cache")
        dbfile = open(dbname, "w")        
        dbfile.write("hejsanhoppsan")
        print "Db file at %s successfully mangled" % dbname
        self.repo = repository.Repo(self.repopath)
        sha256 = self.repo.sha256.get_sha256(DATA3_MD5)
        self.assertEquals(sha256, expected_sha256)
        

if __name__ == '__main__':
    unittest.main()
