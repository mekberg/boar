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

    def tearDown(self):
        shutil.rmtree(self.repopath, ignore_errors = True)

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
        expected_info = {"testkey": "testvalue"}
        committed_info = copy(expected_info)
        writer = self.repo.create_session()
        id = writer.commit(committed_info)
        self.assertEqual(committed_info, expected_info,
                         "Given info dict was changed during commit")
        reader = self.repo.get_session(id)
        self.assertEqual(expected_info, reader.session_info,
                         "Read info differs from committed info")

    def test_simple_blob(self):
        expected_info = {"filename": "testfilename.txt",
                         "md5sum": DATA1_MD5}
        committed_info = copy(expected_info)
        writer = self.repo.create_session()
        #def add(self, data, metadata, original_sum):
        writer.add(DATA1, committed_info)
        self.assertEqual(committed_info, expected_info)
        id = writer.commit()
        reader = self.repo.get_session(id)
        blobinfos = list(reader.get_all_blob_infos())
        self.assertEqual(blobinfos, [expected_info])

if __name__ == '__main__':
    unittest.main()
