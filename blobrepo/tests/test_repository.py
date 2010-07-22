import sys, os, unittest, tempfile, shutil
from copy import copy

DATA1 = "tjosan"
DATA1_MD5 = "5558e0551622725a5fa380caffa94c5d"
DATA2 = "tjosan hejsan"
DATA2_MD5 = "923574a1a36aebc7e1f586b7d363005e"

TMPDIR="/tmp"

if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from blobrepo import repository

class TestBlobRepo(unittest.TestCase):
    def setUp(self):
        self.repopath = tempfile.mktemp(dir=TMPDIR)
        repository.create_repository(self.repopath)
        self.repo = repository.Repo(self.repopath)
        self.sessioninfo1 = {"foo": "bar"}
        self.fileinfo1 = {"filename": "testfilename.txt",
                          "md5sum": DATA1_MD5}
        self.fileinfo2 = {"filename": "testfilename2.txt",
                          "md5sum": DATA2_MD5}

    def tearDown(self):
        shutil.rmtree(self.repopath, ignore_errors = True)

    def assertListsEqualAsSets(self, lst1, lst2):
        self.assertEqual(len(lst1), len(lst2))
        for i in lst1:
            self.assert_(i in lst2)
        for i in lst2:
            self.assert_(i in lst1)

    def test_empty_commit(self):
        writer = self.repo.create_session()
        id = writer.commit()        
        self.assertEqual(1, id, "Session ids starts from 1") 
        self.assertEqual(self.repo.get_all_sessions(), [1], 
                         "There should be exactly one session")

    def test_double_commit(self):
        writer = self.repo.create_session()
        writer.commit()        
        self.assertRaises(Exception, writer.commit)        
        
    def test_session_info(self):
        committed_info = copy(self.sessioninfo1)
        writer = self.repo.create_session()
        id = writer.commit(committed_info)
        self.assertEqual(committed_info, self.sessioninfo1,
                         "Given info dict was changed during commit")
        reader = self.repo.get_session(id)
        self.assertEqual(self.sessioninfo1, reader.session_info,
                         "Read info differs from committed info")

    def test_simple_blob(self):
        committed_info = copy(self.fileinfo1)
        writer = self.repo.create_session()
        writer.add_blob_data(DATA1_MD5, DATA1)
        writer.add(committed_info)
        self.assertEqual(committed_info, self.fileinfo1)
        id = writer.commit()
        reader = self.repo.get_session(id)
        blobinfos = list(reader.get_all_blob_infos())
        self.assertEqual(blobinfos, [self.fileinfo1])

    def test_secondary_session(self):
        writer1 = self.repo.create_session()
        writer1.add_blob_data(DATA1_MD5, DATA1)
        writer1.add(self.fileinfo1)
        id1 = writer1.commit()
        writer2 = self.repo.create_session(base_session = id1)
        writer2.add_blob_data(DATA2_MD5, DATA2)
        writer2.add(self.fileinfo2)
        id2 = writer2.commit()
        reader = self.repo.get_session(id2)
        blobinfos = list(reader.get_all_blob_infos())
        self.assertListsEqualAsSets(blobinfos, [self.fileinfo1, self.fileinfo2])

    def test_remove(self):
        writer1 = self.repo.create_session()
        writer1.add_blob_data(DATA1_MD5, DATA1)
        writer1.add(self.fileinfo1)
        id1 = writer1.commit()
        writer2 = self.repo.create_session(base_session = id1)
        writer2.remove(self.fileinfo1['filename'])
        id2 = writer2.commit()
        blobinfos = list(self.repo.get_session(id1).get_all_blob_infos())
        self.assertEqual(blobinfos, [self.fileinfo1])
        blobinfos = list(self.repo.get_session(id2).get_all_blob_infos())
        self.assertEqual(blobinfos, [])

    def test_remove_nonexisting(self):
        writer1 = self.repo.create_session()
        self.assertRaises(Exception, writer1.remove, "doesnotexist.txt")        

if __name__ == '__main__':
    unittest.main()
