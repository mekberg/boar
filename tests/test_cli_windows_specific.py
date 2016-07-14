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
import sys, os, unittest, tempfile, shutil
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
        self.testdir = tempfile.mkdtemp(prefix="boar_test_cli_")
        os.chdir(self.testdir)
        call([BOAR, "mkrepo", "TESTREPOåäö"])
        assert os.path.exists("TESTREPOåäö")
        output, returncode = call([BOAR, "mkrepo", "TESTREPOåäö"], check=False)
        assert returncode == 1
        call([BOAR, "--repo", "TESTREPOåäö", "mksession", "TestSessionåäö"])
        assert "ERROR: File or directory already exists" in output

    def tearDown(self):
        os.chdir(BOAR_HOME)
        shutil.rmtree(self.testdir)

    def testCat(self):
        testdata = "a\n\b\n\c"
        call([BOAR, "--repo", "TESTREPOåäö", "co", "TestSessionåäö"])
        write_file("TestSessionåäö/fil.txt", testdata)
        call([BOAR, "ci"], cwd="TestSessionåäö")
        output, returncode = call([BOAR, "--repo", "TESTREPOåäö", "cat", "TestSessionåäö/fil.txt"])
        self.assertEqual(output, testdata)

    def testLogWorkdir(self):
        testdata = "Tjosan\nHejsan\n"
        call([BOAR, "--repo", "TESTREPOåäö", "co", "TestSessionåäö"])
        os.mkdir("TestSessionåäö/a/")
        write_file("TestSessionåäö/a/fil.txt", testdata)
        call([BOAR, "ci"], cwd="TestSessionåäö/a")
        output, returncode = call([BOAR, "log", "fil.txt"], cwd="TestSessionåäö/a")
        assert "r2 | " in output
        assert returncode == 0

class TestCliWindowsSpecific(unittest.TestCase):
    def setUp(self):
        self.testdir = tempfile.mkdtemp(prefix="boar_test_cli_windows_")
        os.chdir(self.testdir)

    def tearDown(self):
        os.chdir(BOAR_HOME)
        shutil.rmtree(self.testdir)

    #
    # Actual tests start here
    #
    def testNoArgs(self):
        output, returncode = call([BOAR], check=False)
        assert "Usage: boar" in output
        assert returncode == 1

    def testMkrepo(self):
        assert not os.path.exists("TESTREPO")
        call([BOAR, "mkrepo", "TESTREPO"])
        assert os.path.exists("TESTREPO")

    def testEmpty(self):
        pass


if __name__ == '__main__':
    unittest.main()

