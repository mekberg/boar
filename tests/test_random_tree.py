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

def backslashes_to_slashes(s):
    return s.replace("\\", "/")


class TestRandomTree(unittest.TestCase):
    def setUp(self):
        self.testdir = tempfile.mkdtemp(prefix="boar_test_random_tree_")
        os.chdir(self.testdir)
        call([BOAR, "mkrepo", "TESTREPO"])
        call([BOAR, "--repo", "TESTREPO", "mksession", "TestSession"])

    def tearDown(self):
        os.chdir(BOAR_HOME)
        shutil.rmtree(self.testdir)


    def _testRandomTree(self, workdir, use_windows_limits, max_path_length, expected_fingerprint):
        manifest_filename = os.path.join(workdir, "manifest-md5.txt")
        r = randtree.RandTree(workdir, use_windows_limits=use_windows_limits, max_path_length=max_path_length)
        r.add_dirs(10)
        r.add_files(50)
        r.write_md5sum(manifest_filename)
        call([BOAR, "--repo", "TESTREPO", "import", workdir, "TestSession"])

        r.modify_files(1)
        output, returncode = call([BOAR, "ci"], cwd = workdir, check = False)
        assert returncode == 1, "Should fail due to manifest error"
        assert "contents conflicts with manifest" in output

        for x in range(0, 20):
            r.delete_files(5)
            r.add_files(5)
            r.modify_files(5)
            r.write_md5sum(manifest_filename)
            call([BOAR, "ci"], cwd = workdir)
            call([BOAR, "--repo", "TESTREPO", "manifests", "TestSession"])
        self.assertEqual(r.fingerprint(), expected_fingerprint)
        # Verify that the workdir contents matches the randtree instance
        self._assertWorkdirEqualsTree(workdir, r)
            
        # Remove the tree and check it out
        shutil.rmtree(workdir)
        call([BOAR, "--repo", "TESTREPO", "co", "TestSession", workdir])

        # Do the check again on the fresh check-out
        self._assertWorkdirEqualsTree(workdir, r)

    def _assertWorkdirEqualsTree(self, workdir, randtree):
        all_files = get_tree(os.path.abspath(workdir), skip = [".boar"])
        all_files.remove("manifest-md5.txt")
        self.assertEqual(set(all_files), set(map(backslashes_to_slashes, randtree.files)))
        for fn in all_files:
            path = os.path.join(workdir, fn)
            self.assertEqual(md5sum(randtree.get_file_data(fn)), md5sum_file(path))


    def testWindowsCompatibleRandomTree(self):
        workdir = u"workdir"
        assert len(workdir) < 50
        self._testRandomTree(workdir=workdir,
                             use_windows_limits=True,
                             max_path_length=200,
                             expected_fingerprint="26f472409c8f4ef3a8250a6bef6739ca")

    def testNormalRandomTree(self):
        if os.name == "nt":
            return # This test will fail on windows, see issue 83
        workdir = u"workdir"
        self._testRandomTree(workdir=workdir,
                             use_windows_limits=True,
                             max_path_length=100000,
                             expected_fingerprint="f014553adf18a403d836e08576db193a")
        manifest_filename = "workdir/manifest-md5.txt"

if __name__ == '__main__':
    unittest.main()

