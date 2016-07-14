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

    def testApplyDelta(self):
        bloblist = boar_common.bloblist_to_dict([
                {'filename': 'unchanged.txt',
                 'md5sum': "00000000000000000000000000000000"},
                {'filename': 'modified.txt',
                 'md5sum': "00000000000000000000000000000001"},
                {'filename': 'deleted.txt',
                 'md5sum': "00000000000000000000000000000002"}])
        delta = [
            {'filename': 'new.txt',
             'md5sum': "00000000000000000000000000000003"},
            {'filename': 'deleted.txt',
             'action': 'remove'},
            {'filename': 'modified.txt',
             'md5sum': "00000000000000000000000000000004"}
            ]
        expected_new_bloblist = [
            {'filename': 'unchanged.txt',
             'md5sum': "00000000000000000000000000000000"},
            {'filename': 'modified.txt',
             'md5sum': "00000000000000000000000000000004"},
            {'filename': 'new.txt',
             'md5sum': "00000000000000000000000000000003"}
            ]

        boar_common.apply_delta(bloblist, delta)
        self.assertEquals(sorted(bloblist.values()), sorted(expected_new_bloblist))


    def testBloblistDelta(self):
        bloblist1 = [
            {'filename': 'unchanged.txt',
             'md5sum': "00000000000000000000000000000000"},
            {'filename': 'modified.txt',
             'md5sum': "00000000000000000000000000000001"},
            {'filename': 'deleted.txt',
             'md5sum': "00000000000000000000000000000002"}]
        bloblist2 = [
            {'filename': 'unchanged.txt',
             'md5sum': "00000000000000000000000000000000"},
            {'filename': 'modified.txt',
             'md5sum': "00000000000000000000000000000004"},
            {'filename': 'new.txt',
             'md5sum': "00000000000000000000000000000003"}
            ]
        expected_delta = boar_common.sorted_bloblist([
                {'filename': 'new.txt',
                 'md5sum': "00000000000000000000000000000003"},
                {'filename': 'deleted.txt',
                 'action': 'remove'},
                {'filename': 'modified.txt',
                 'md5sum': "00000000000000000000000000000004"}
                ])
        original_bloblist1_repr = repr(bloblist1)
        original_bloblist2_repr = repr(bloblist2)
        delta = boar_common.sorted_bloblist(boar_common.bloblist_delta(bloblist1, bloblist2))

        self.assertEquals(delta, expected_delta)

        # Make sure the original bloblists are unchanged
        self.assertEquals(original_bloblist1_repr, repr(bloblist1))
        self.assertEquals(original_bloblist2_repr, repr(bloblist2))


    def testSortedBloblist(self):
        a, b, c = ({'filename': 'a.txt',
                    'md5sum': "00000000000000000000000000000000"},
                   {'filename': 'b.txt',
                    'md5sum': "00000000000000000000000000000001"},
                   {'filename': 'c.txt',
                    'md5sum': "00000000000000000000000000000002"})
        unsorted_bloblist = [c, a, b]
        unsorted_bloblist_repr = repr(unsorted_bloblist)
        expected_sorted_bloblist = [a, b, c]
        sorted_bloblist = boar_common.sorted_bloblist(unsorted_bloblist)
        self.assertEquals(sorted_bloblist, expected_sorted_bloblist)
        # Make sure the original is untouched
        self.assertEquals(repr(unsorted_bloblist), unsorted_bloblist_repr)


if __name__ == '__main__':
    unittest.main()

