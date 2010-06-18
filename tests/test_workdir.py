from __future__ import with_statement
import sys, os, unittest, tempfile, shutil
from copy import copy

DATA1 = "tjosan"
DATA1_MD5 = "5558e0551622725a5fa380caffa94c5d"
DATA2 = "tjosan hejsan"
DATA2_MD5 = "923574a1a36aebc7e1f586b7d363005e"

TMPDIR="/tmp"

if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import workdir
from blobrepo import repository

class TestWorkdir(unittest.TestCase):
    def setUp(self):
        self.workdir = tempfile.mktemp(prefix='workdir_', dir=TMPDIR)
        self.repopath = tempfile.mktemp(prefix='workdir_repo_', dir=TMPDIR)
        repository.create_repository(self.repopath)
        #os.mkdir(self.workdir)
        #self.wd = workdir.Workdir(self.repopath, "TestSession", None, self.workdir)

    def initWorkdir(self):
        os.mkdir(self.workdir)
        self.wd = workdir.Workdir(self.repopath, "TestSession", None, self.workdir)
        self.wd.checkin()

    def tearDown(self):
        shutil.rmtree(self.workdir, ignore_errors = True)
        shutil.rmtree(self.repopath, ignore_errors = True)

    def testEmpty(self):
        self.initWorkdir()
        changes = self.wd.get_changes()
        self.assertEqual(changes, ([], [], [], [], []))

    def testSimpleCheckin(self):
        self.initWorkdir()
        self.addWorkdirFile("tjosan.txt", "tjosanhejsan")
        changes = self.wd.get_changes()
        self.assertEqual(changes, ([], ["tjosan.txt"], [], [], []))
        self.wd.checkin()
        changes = self.wd.get_changes()
        self.assertEqual(changes, (["tjosan.txt"], [], [], [], []))

    def addWorkdirFile(self, path, content):
        filepath = os.path.join(self.workdir, path)
        with open(filepath, "w") as f:
            f.write(content)

if __name__ == '__main__':
    unittest.main()
