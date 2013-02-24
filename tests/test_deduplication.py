# -*- coding: utf-8 -*-

# Copyright 2010 Mats Ekberg
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

import sys, os, unittest, shutil

if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import workdir

from blobrepo import repository
repository.DEDUP_BLOCK_SIZE = 3 # Make deduplication cases more manageble

from common import get_tree, my_relpath, convert_win_path_to_unix, md5sum, DevNull
from boar_exceptions import UserError
from front import Front
from wdtools import read_tree, write_tree, WorkdirHelper, boar_dirs
from deduplication import print_recipe

class TestDeduplication(unittest.TestCase, WorkdirHelper):
    def setUp(self):
        self.remove_at_teardown = []
        self.workdir = self.createTmpName()
        self.repopath = self.createTmpName()
        repository.create_repository(self.repopath)
        os.mkdir(self.workdir)
        self.wd = workdir.Workdir(self.repopath, u"TestSession", u"", None, self.workdir)
        self.wd.setLogOutput(DevNull())
        self.wd.use_progress_printer(False)
        self.repo = self.wd.front.repo
        id = self.wd.get_front().mksession(u"TestSession")
        assert id == 1

    def testMultiplePossibleHits1(self):
        self.addWorkdirFile("a.txt", "aaabbbcccaaabbbaaabbbaaabbb")
        self.wd.checkin()
        blob = self.addWorkdirFile("b.txt", "Xaaabbbcccaaabbbaaabbbaaabbb")
        self.wd.checkin()
        recipe = self.repo.get_recipe(blob)
        self.assertEquals(len(recipe['pieces']), 2)
        self.assertEquals(recipe['pieces'][0], {
                'source': '02129bb861061d1a052c592e2dc6b383', 
                'repeat': 1, 'original': True, 'offset': 0, 'size': 1})
        self.assertEquals(recipe['pieces'][1], {
                'source': '00312b74e44d0712882387b8e0f0a57e', 
                'repeat': 1, 'original': False, 'offset': 0, 'size': 27})
        rebuilt_content = self.wd.front.get_blob(blob).read()
        self.assertEquals(md5sum(rebuilt_content), "407badd3ba116d47c556d1366343048c")

    def testMultiplePossibleHits2(self):
        first_blob = self.addWorkdirFile("a.txt", "aaabbbaaabbbaaabbbaaabbbccc")
        self.wd.checkin()
        blob = self.addWorkdirFile("b.txt", "aaabbbccc")
        self.wd.checkin()
        recipe = self.repo.get_recipe(blob)
        #print_recipe(recipe)
        self.assertEquals(len(recipe['pieces']), 1)
        self.assertEquals(recipe['pieces'][0], {
                'source': first_blob, 
                'repeat': 1, 'original': False, 'offset': 18, 'size': 9})
        rebuilt_content = self.wd.front.get_blob(blob).read()
        self.assertEquals(md5sum(rebuilt_content), "d1aaf4767a3c10a473407a4e47b02da6")

    def testSplitMatch(self):
        a_blob = self.addWorkdirFile("a.txt", "aaa")
        b_blob = self.addWorkdirFile("b.txt", "bbb")
        self.wd.checkin()
        c_blob = self.addWorkdirFile("c.txt", "aaabbb")
        self.wd.checkin()
        recipe = self.repo.get_recipe(c_blob)
        #print_recipe(recipe)
        self.assertEquals(len(recipe['pieces']), 2)
        self.assertEquals(recipe['pieces'][1], {
                'source': b_blob, 
                'repeat': 1, 'original': False, 'offset': 0, 'size': 3})
        rebuilt_content = self.wd.front.get_blob(c_blob).read()
        self.assertEquals(md5sum(rebuilt_content), "6547436690a26a399603a7096e876a2d")

    def testInterleavedHit(self):
        a_blob = self.addWorkdirFile("a.txt", "aaa")
        self.wd.checkin()
        b_blob = self.addWorkdirFile("b.txt", "XaaaXaaaX")
        self.wd.checkin()
        x_blob = md5sum("X")
        recipe = self.repo.get_recipe(b_blob)
        #print_recipe(recipe)
        self.assertEquals(len(recipe['pieces']), 5)
        self.assertEquals(recipe['pieces'][0], {
                'source': x_blob, 
                'repeat': 1, 'original': True, 'offset': 0, 'size': 1})
        self.assertEquals(recipe['pieces'][1], {
                'source': a_blob, 
                'repeat': 1, 'original': False, 'offset': 0, 'size': 3})
        self.assertEquals(recipe['pieces'][2], {
                'source': x_blob, 
                'repeat': 1, 'original': True, 'offset': 0, 'size': 1})
        self.assertEquals(recipe['pieces'][3], {
                'source': a_blob, 
                'repeat': 1, 'original': False, 'offset': 0, 'size': 3})
        self.assertEquals(recipe['pieces'][4], {
                'source': x_blob, 
                'repeat': 1, 'original': True, 'offset': 0, 'size': 1})
        rebuilt_content = self.wd.front.get_blob(b_blob).read()
        self.assertEquals(md5sum(rebuilt_content), "e18585992d1ea79a30a34e015c49719e")
        
    def tearDown(self):
        for d in self.remove_at_teardown:
            shutil.rmtree(d, ignore_errors = True)

if __name__ == '__main__':
    unittest.main()
