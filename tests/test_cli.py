# -*- coding: utf-8 -*-

# Copyright 2012 Mats Ekberg
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
import sys, os, unittest, tempfile, shutil, json
import subprocess

if __name__ == '__main__':
    boar_home = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, boar_home)
    sys.path.insert(0, os.path.join(boar_home, "macrotests"))

import randtree
from common import get_tree, md5sum, md5sum_file

def call(cmd, check=True, cwd=None):
    """Execute a command and return output and status code. If 'check' is True,
    an exception will be raised if the command exists with an error code. If
    'cwd' is set, the command will execute in that directory."""
    def localencoding(us):
        if type(us) == unicode:
            if os.name == "nt":
                return us.encode("mbcs")
            else:
                return us.encode("utf8")
        return us
    cmd = [localencoding(s) for s in cmd]
    cwd = localencoding(cwd)
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, cwd=cwd)
    stdout = p.communicate()[0]
    returncode = p.poll()
    if check and returncode != 0:
        raise Exception("Call failed with errorcode %s: %s" % (returncode, stdout))  
    return stdout, returncode

BOAR_HOME = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if __name__ == '__main__':
    sys.path.insert(0, BOAR_HOME)

if os.name == "nt":
    BOAR = os.path.join(BOAR_HOME, "boar.bat")
else:
    BOAR = os.path.join(BOAR_HOME, "boar")

def write_file(path, contents):
    with open(path, "wb") as f:
        f.write(contents)

class TestCli(unittest.TestCase):
    def setUp(self):
        self.testdir = tempfile.mkdtemp(prefix = self.__class__.__name__ + "_")
        os.chdir(self.testdir)
        self.setupRepo(u"TESTREPOåäö")
        self.setupSession(u"TestSessionåäö")

    def setupRepo(self, name):
        assert os.path.sep not in name
        call([BOAR, "mkrepo", name])
        assert os.path.exists(name)
        global REPO
        REPO = name

    def setupWorkdir(self, session, wdname = None, offset = ""):
        if wdname == None:
            wdname = session
        if offset:
            call([BOAR, "--repo", REPO, "co", session + "/" + offset, wdname])
        else:
            call([BOAR, "--repo", REPO, "co", session, wdname])
        global WORKDIR
        WORKDIR = wdname

    def setupSession(self, name):
        call([BOAR, "--repo", REPO, "mksession", name])
        global SESSION
        SESSION = name

    def tearDown(self):
        global REPO, SESSION, WORKDIR
        os.chdir(BOAR_HOME)
        shutil.rmtree(self.testdir)
        if "REPO" in globals(): del REPO,
        if "SESSION" in globals(): del SESSION
        if "WORKDIR" in globals(): del WORKDIR

    def testCat(self):
        testdata = "a\n\b\n\c"
        call([BOAR, "--repo", REPO, "co", SESSION])
        write_file(os.path.join(SESSION, "fil.txt"), testdata)
        call([BOAR, "ci"], cwd=SESSION)
        output, returncode = call([BOAR, "--repo", REPO, "cat", os.path.join(SESSION, "fil.txt")])
        self.assertEqual(output, testdata)

    def testLogWorkdir(self):
        testdata = "Tjosan\nHejsan\n"
        call([BOAR, "--repo", REPO, "co", SESSION])
        os.mkdir(os.path.join(SESSION, "a"))
        write_file(os.path.join(SESSION, "a/fil.txt"), testdata)
        call([BOAR, "ci"], cwd=os.path.join(SESSION, "a"))
        output, returncode = call([BOAR, "log", "fil.txt"], cwd=os.path.join(SESSION, "a"))
        assert "r2 | " in output
        assert returncode == 0

    def testPartialCommit(self):
        self.setupWorkdir(SESSION)
        file_new = "file_new.txt"
        file_modified = "file_modified.txt"
        file_deleted = "file_deleted.txt"
        file_notincluded = "file_notincluded.txt"
        file_unchanged = "file_unchanged.txt"

        # Prepare initial conditions
        write_file(os.path.join(WORKDIR, file_modified), "original contents")
        write_file(os.path.join(WORKDIR, file_unchanged), "unchanged contents")
        write_file(os.path.join(WORKDIR, file_deleted), "deleted contents")
        call([BOAR, "ci"], cwd=WORKDIR)

        # Set up the workdir for the partial commit
        write_file(os.path.join(WORKDIR, file_modified), "modified")
        os.unlink(os.path.join(WORKDIR, file_deleted))
        write_file(os.path.join(WORKDIR, file_new), "new")
        write_file(os.path.join(WORKDIR, file_notincluded), "not included")
        
        output, returncode = call([BOAR, "ci", file_new, file_modified, file_deleted], cwd=WORKDIR)
        assert "Checked in session id 3" in output
        output, returncode = call([BOAR,  "--repo", REPO, 
                                   "contents", "-r", "3", SESSION])
        self.assertEqual(sorted(json.loads(output)['files']),
                              sorted([{"filename": "file_unchanged.txt",
                                "size": 18,
                                "md5": "eeefefca582568aabfbca7f5fce6a20a"
                                },
                               {"filename": "file_modified.txt",
                                "size": 8,
                                "md5": "9ae73c65f418e6f79ceb4f0e4a4b98d5"
                                },
                               {"filename": "file_new.txt",
                                "size": 3,
                                "md5": "22af645d1859cb5ca6da0c484f1f37ea"
                                }]))

    def testPartialCommitInOffsetWorkdir(self):
        self.setupWorkdir(SESSION, offset="subdir1")
        file_new = "file_new.txt"
        file_modified = "file_modified.txt"
        file_deleted = "file_deleted.txt"
        file_notincluded = "file_notincluded.txt"
        file_unchanged = "file_unchanged.txt"

        subdir2 = os.path.join(WORKDIR, "subdir2")
        os.mkdir(subdir2)

        # Prepare initial conditions
        write_file(os.path.join(subdir2, file_modified), "original contents")
        write_file(os.path.join(subdir2, file_unchanged), "unchanged contents")
        write_file(os.path.join(subdir2, file_deleted), "deleted contents")
        call([BOAR, "ci"], cwd=WORKDIR)

        # Set up the workdir for the partial commit
        write_file(os.path.join(subdir2, file_modified), "modified")
        os.unlink(os.path.join(subdir2, file_deleted))
        write_file(os.path.join(subdir2, file_new), "new")
        write_file(os.path.join(subdir2, file_notincluded), "not included")
        
        output, returncode = call([BOAR, "ci", 
                                   os.path.join("subdir2", file_new), 
                                   os.path.join("subdir2", file_modified), 
                                   os.path.join("subdir2", file_deleted)], cwd=WORKDIR)
        assert "Checked in session id 3" in output
        output, returncode = call([BOAR,  "--repo", REPO, 
                                   "contents", "-r", "3", SESSION])
        self.assertEqual(sorted(json.loads(output)['files']),
                              sorted([{"filename": "subdir1/subdir2/file_unchanged.txt",
                                "size": 18,
                                "md5": "eeefefca582568aabfbca7f5fce6a20a"
                                },
                               {"filename": "subdir1/subdir2/file_modified.txt",
                                "size": 8,
                                "md5": "9ae73c65f418e6f79ceb4f0e4a4b98d5"
                                },
                               {"filename": "subdir1/subdir2/file_new.txt",
                                "size": 3,
                                "md5": "22af645d1859cb5ca6da0c484f1f37ea"
                                }]))


if __name__ == '__main__':
    unittest.main()

