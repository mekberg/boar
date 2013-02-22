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

class TestWorkdir(unittest.TestCase, WorkdirHelper):
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
        self.assertEquals(recipe['pieces'][0], {u'source': u'02129bb861061d1a052c592e2dc6b383', 
                                                u'repeat': 1, 
                                                u'original': True, 
                                                u'offset': 0, 
                                                u'size': 1})
        self.assertEquals(recipe['pieces'][1], {u'source': u'00312b74e44d0712882387b8e0f0a57e', 
                                                u'repeat': 1, 
                                                u'original': False, 
                                                u'offset': 0, 
                                                u'size': 27})
        rebuilt_content = self.wd.front.get_blob(blob).read()
        self.assertEquals(md5sum(rebuilt_content), "407badd3ba116d47c556d1366343048c")
        
    def tearDown(self):
        for d in self.remove_at_teardown:
            shutil.rmtree(d, ignore_errors = True)

if __name__ == '__main__':
    unittest.main()
