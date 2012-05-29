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

def call(cmd):
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    stdout = p.communicate()[0]
    returncode = p.poll()
    return stdout, returncode

BOAR_HOME = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if __name__ == '__main__':
    sys.path.insert(0, BOAR_HOME)

if os.name == "nt":
    BOAR = os.path.join(BOAR_HOME, "boar.bat")
else:
    BOAR = os.path.join(BOAR_HOME, "boar")

class TestCliWindowsSpecific(unittest.TestCase):
    def setUp(self):
        self.testdir = tempfile.mkdtemp(prefix="boar_test_cli_")
        os.chdir(self.testdir)
        print self.testdir
    
    def tearDown(self):
        os.chdir(BOAR_HOME)
        shutil.rmtree(self.testdir)

    #
    # Actual tests start here
    #

    def testNoArgs(self):
        output, returncode = call([BOAR])
        assert "Usage: boar" in output
        assert returncode == 1

    def testMkrepo(self):
        assert not os.path.exists("TESTREPO")
        output, returncode = call([BOAR, "mkrepo", "TESTREPO"])
        assert returncode == 0
        assert os.path.exists("TESTREPO")

    def testEmpty(self):
        pass


if __name__ == '__main__':
    unittest.main()

