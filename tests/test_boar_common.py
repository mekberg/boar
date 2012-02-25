# -*- coding: utf-8 -*-

# Copyright 2011 Mats Ekberg
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

TMPDIR=tempfile.gettempdir()

if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import boar_common

def create_file(directory, filename, data = ""):
    path = os.path.join(directory, filename)
    with open(path, "w") as f:
        f.write(data)
    return path

class Test(unittest.TestCase):
    def setUp(self):
        pass
        
    def testSafeDelete(self):
        tmpdir = tempfile.mkdtemp(prefix='testboarcommon_', dir=TMPDIR)
        data = "some data"
        
        # This is a normal file, should be deleted
        path = create_file(tmpdir, "deleteme.txt", data)
        self.assertTrue(os.path.exists(path))
        boar_common.safe_delete_file(path)
        self.assertTrue(not os.path.exists(path))

        # These files should not be deleted
        path = create_file(tmpdir, "1b4ffbffb3db2add523ebe25312f4526", data)
        self.assertRaises(AssertionError, boar_common.safe_delete_file, path)
        self.assertTrue(os.path.exists(path))
        path = create_file(tmpdir, "session.json", data)
        self.assertRaises(AssertionError, boar_common.safe_delete_file, path)
        self.assertTrue(os.path.exists(path))
        path = create_file(tmpdir, "bloblist.json", data)
        self.assertRaises(AssertionError, boar_common.safe_delete_file, path)
        self.assertTrue(os.path.exists(path))
        path = create_file(tmpdir, "1b4ffbffb3db2add523ebe25312f4526.fingerprint", data)
        self.assertRaises(AssertionError, boar_common.safe_delete_file, path)
        self.assertTrue(os.path.exists(path))
        path = create_file(tmpdir, "1b4ffbffb3db2add523ebe25312f4526.recipe", data)
        self.assertRaises(AssertionError, boar_common.safe_delete_file, path)
        self.assertTrue(os.path.exists(path))

        shutil.rmtree(tmpdir, ignore_errors = True)

        

if __name__ == '__main__':
    unittest.main()

