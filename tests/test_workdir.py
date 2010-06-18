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
        os.mkdir(self.workdir)
        repository.create_repository(self.repopath)
        self.wd = workdir.Workdir(self.repopath, "TestSession", None, self.workdir)

    def tearDown(self):
        shutil.rmtree(self.workdir, ignore_errors = True)
        shutil.rmtree(self.repopath, ignore_errors = True)

    def testEmpty(self):
        self.wd.checkin()

    def testSimpleCheckin(self):
        self.addWorkdirFile("tjosan.txt", "tjosanhejsan")
        self.wd.checkin()

    def addWorkdirFile(self, path, content):
        filepath = os.path.join(self.workdir, path)
        with open(filepath, "w") as f:
            f.write(content)

if __name__ == '__main__':
    unittest.main()
