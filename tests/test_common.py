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
import sys, os, unittest, tempfile

TMPDIR=tempfile.gettempdir()

if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import common

class TestStrictFileWriterBasics(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix='testcommon_', dir=TMPDIR)
        self.filename = os.path.join(self.tmpdir, "test.txt")

    def testEmptyFile(self):
        sfw = common.StrictFileWriter(self.filename, "d41d8cd98f00b204e9800998ecf8427e", 0)
        sfw.close()
        self.assertEquals("", open(self.filename).read())
        
class TestStrictFileWriterEnforcement(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix='testcommon_', dir=TMPDIR)
        self.filename = os.path.join(self.tmpdir, "avocado.txt")
        self.sfw = common.StrictFileWriter(self.filename, "6118fda28fbc20966ba8daafdf836683", len("avocado"))

    def testExisting(self):
        self.sfw.write("avocado")
        self.sfw.close()
        self.assertRaises(common.ConstraintViolation, common.StrictFileWriter, self.filename, \
                              "fe01d67a002dfa0f3ac084298142eccd", len("orange"))
        self.assertEquals("avocado", open(self.filename).read())

    def testOverrun(self):
        self.assertRaises(common.ConstraintViolation, self.sfw.write, "avocadoo")

    def testOverrun2(self):
        self.sfw.write("avo")
        self.sfw.write("cad")
        self.sfw.write("o")
        self.assertRaises(common.ConstraintViolation, self.sfw.write, "o")

    def testUnderrun(self):
        self.sfw.write("avocad")
        self.assertRaises(common.ConstraintViolation, self.sfw.close)

    def testHappyPath(self):
        self.sfw.write("avocado")
        self.sfw.close()
        self.assertEquals("avocado", open(self.filename).read())

    def testHappyPath2(self):
        self.sfw.write("avo")
        self.sfw.write("cad")
        self.sfw.write("")
        self.sfw.write("o")
        self.sfw.close()
        self.assertEquals("avocado", open(self.filename).read())

    def testWrongChecksum(self):
        self.assertRaises(common.ConstraintViolation, self.sfw.write, "avocato")

if __name__ == '__main__':
    unittest.main()

