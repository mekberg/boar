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

if os.getenv("BOAR_SKIP_DEDUP_TESTS") == "1":
    print "Skipping test_deduplication.py due to BOAR_SKIP_DEDUP_TESTS"
    sys.exit(0)

if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import workdir

from blobrepo import repository
repository.DEDUP_BLOCK_SIZE = 3 # Make deduplication cases more manageble

from common import get_tree, my_relpath, convert_win_path_to_unix, md5sum, DevNull
from boar_exceptions import UserError
from front import Front, verify_repo
from wdtools import read_tree, write_tree, WorkdirHelper, boar_dirs, write_file

from deduplication import print_recipe
from deduplication import RecipeFinder
from deduplication import BlocksDB
from cdedup import IntegerSet, calc_rolling

class FakePieceHandler:
    def init_piece(self, index): pass
    def add_piece_data(self, index, data): pass
    def end_piece(self, index): return ("FAKEBLOB", 0)

class TestRecipeFinder(unittest.TestCase, WorkdirHelper):
    def setUp(self):
        self.remove_at_teardown = []
        self.dbname = self.createTmpName()
        self.blocksdb = BlocksDB(self.dbname, 3)
        self.piece_handler = FakePieceHandler()
        self.integer_set = IntegerSet(1)

    def testSimpleUnaligned(self):
        self.integer_set.add(3298534883712) # "aaa"
        recipe_finder = RecipeFinder(self.blocksdb, 3, self.integer_set, None, original_piece_handler = self.piece_handler)
        self.blocksdb.begin()
        self.blocksdb.add_block("47bce5c74f589f4867dbd57e9ca9f808", 0, "47bce5c74f589f4867dbd57e9ca9f808")
        self.blocksdb.commit() 
        recipe_finder.feed("XX")
        recipe_finder.feed("Xa")
        recipe_finder.feed("aa")
        recipe_finder.close()
        recipe = recipe_finder.get_recipe()
        self.assertEquals(recipe, {'md5sum': '5afc35e6684b843ceb498f5031f22660',
                                   'method': 'concat', 'size': 6,
                                   'pieces': [{'source': 'FAKEBLOB', 'size': 3L,
                                               'original': True, 'repeat': 1, 'offset': 0},
                                              {'source': u'47bce5c74f589f4867dbd57e9ca9f808', 'size': 3,
                                               'original': False, 'repeat': 1, 'offset': 0}]
                                   })
        #print recipe

class TestConcurrentCommit(unittest.TestCase, WorkdirHelper):
    def setUp(self):
        self.remove_at_teardown = []
        self.workdir1 = self.createTmpName()
        self.workdir2 = self.createTmpName()
        self.repopath = self.createTmpName()
        repository.create_repository(self.repopath, enable_deduplication = True)

        os.mkdir(self.workdir1)
        self.wd1 = workdir.Workdir(self.repopath, u"TestSession1", u"", None, self.workdir1)
        self.wd1.setLogOutput(DevNull())
        self.wd1.use_progress_printer(False)
        self.wd1.get_front().mksession(u"TestSession1")

        os.mkdir(self.workdir2)
        self.wd2 = workdir.Workdir(self.repopath, u"TestSession2", u"", None, self.workdir2)
        self.wd2.setLogOutput(DevNull())
        self.wd2.use_progress_printer(False)
        self.wd2.get_front().mksession(u"TestSession2")

    def testIdenticalCommits(self):
        write_file(self.workdir1, "a.txt", "aaa")
        self.wd1.checkin()

        write_file(self.workdir2, "b2.txt", "aaaaaa")
        write_file(self.workdir1, "b1.txt", "aaaaaa")

        # Make the checkin() go just almost all the way...
        wd2_commit = self.wd2.front.commit
        self.wd2.front.commit = lambda session_name, log_message: None

        self.wd2.checkin() # Will not complete
        self.wd1.checkin()

        wd2_commit(u"TestSession2", None) # Resume the commit

    def testIdenticalNewBlob(self):
        write_file(self.workdir1, "a.txt", "aaa")
        write_file(self.workdir1, "b.txt", "bbb")
        self.wd1.checkin()

        write_file(self.workdir1, "c1.txt", "aaaccc")
        write_file(self.workdir2, "c2.txt", "bbbccc")

        # Make the checkin() go just almost all the way...
        wd2_commit = self.wd2.front.commit
        self.wd2.front.commit = lambda session_name, log_message: None

        self.wd2.checkin() # Will not complete
        self.wd1.checkin()

        wd2_commit(u"TestSession2", None) # Resume the commit
        self.assertEquals("ccc", self.wd1.front.get_blob("9df62e693988eb4e1e1444ece0578579").read())

    def testRedundantNewBlob(self):
        # aaa    47bce5c74f589f4867dbd57e9ca9f808
        # bbb    08f8e0260c64418510cefb2b06eee5cd
        # ccc    9df62e693988eb4e1e1444ece0578579
        # bbbccc 71d27475242f6b50db02ddf1476107ee

        write_file(self.workdir1, "a.txt", "aaa")
        self.wd1.checkin()

        write_file(self.workdir2, "b.txt", "aaabbbccc")
        # b.txt is deduplicated to aaa + bbbccc
        # Make the checkin() go just almost all the way...
        wd2_commit = self.wd2.front.commit
        self.wd2.front.commit = lambda session_name, log_message: None
        self.wd2.checkin() # Will not complete

        # Is deduplicated to aaa + bbb
        write_file(self.workdir1, "b.txt", "aaabbb")
        self.wd1.checkin() 

        # Is deduplicated to aaa + bbb + ccc
        write_file(self.workdir1, "b.txt", "aaabbbccc")
        self.wd1.checkin() 

        wd2_commit(u"TestSession2", None) # Resume the commit
        self.assertEquals(set(), self.wd1.front.repo.get_orphan_blobs())

    def testThatTrimmedBlobsAreRemovedFromDb(self):
        # aaa    47bce5c74f589f4867dbd57e9ca9f808
        # bbb    08f8e0260c64418510cefb2b06eee5cd
        # ccc    9df62e693988eb4e1e1444ece0578579
        # bbbccc 71d27475242f6b50db02ddf1476107ee

        write_file(self.workdir2, "bbbccc.txt", "bbbccc")

        # Make the checkin() go just almost all the way...
        wd2_commit = self.wd2.front.commit
        self.wd2.front.commit = lambda session_name, log_message: None
        self.wd2.checkin() # Will not complete

        # Now, make sure bbbccc exists as a recipe
        write_file(self.workdir1, "bbb.txt", "bbb")
        write_file(self.workdir1, "ccc.txt", "ccc")
        self.wd1.checkin()

        write_file(self.workdir1, "bbbccc.txt", "bbbccc")
        self.wd1.checkin()

        wd2_commit(u"TestSession2", None) # Resume the commit

        #####################

        # Is deduplicated to bbbccc + X
        # If bbbccc is stored in the blocksdb, the commit will fail
        write_file(self.workdir1, "b.txt", "bbbcccX")
        self.wd1.checkin() 

        self.assertEquals(set(), self.wd1.front.repo.get_orphan_blobs())

    def testIdenticalBlocksOnlyAddedOnce(self):
        write_file(self.workdir1, "a.txt", "aaa")
        write_file(self.workdir2, "b.txt", "aaa")

        # Make the checkin() go just almost all the way...
        wd2_commit = self.wd2.front.commit
        self.wd2.front.commit = lambda session_name, log_message: None

        self.wd2.checkin() # Will not complete
        self.wd1.checkin()
        wd2_commit(u"TestSession2", None) # Resume the commit
        for blockdb in (self.wd1.front.repo.blocksdb, self.wd2.front.repo.blocksdb):
            self.assertEquals(blockdb.get_all_rolling(), [3298534883712])
            self.assertTrue(blockdb.has_block("47bce5c74f589f4867dbd57e9ca9f808"))
            block_locations = blockdb.get_block_locations("47bce5c74f589f4867dbd57e9ca9f808")
            self.assertEquals(list(block_locations), [('47bce5c74f589f4867dbd57e9ca9f808', 0)])

    def tearDown(self):
        verify_repo(self.wd1.get_front())
        for d in self.remove_at_teardown:
            shutil.rmtree(d, ignore_errors = True)
        
        
class TestDeduplicationWorkdir(unittest.TestCase, WorkdirHelper):
    def setUp(self):
        self.remove_at_teardown = []
        self.workdir = self.createTmpName()
        self.repopath = self.createTmpName()
        repository.create_repository(self.repopath, enable_deduplication = True)
        os.mkdir(self.workdir)
        self.wd = workdir.Workdir(self.repopath, u"TestSession", u"", None, self.workdir)
        self.wd.setLogOutput(DevNull())
        self.wd.use_progress_printer(False)
        self.repo = self.wd.front.repo
        id = self.wd.get_front().mksession(u"TestSession")
        assert id == 1

    def testThatRepeatedHitsAreFound(self):
        self.addWorkdirFile("a.txt", "aaa")
        self.wd.checkin()
        blob = self.addWorkdirFile("b.txt", "aaaaaa")
        self.wd.checkin()
        recipe = self.repo.get_recipe(blob)
        self.assertEquals(len(recipe['pieces']), 1)
        rebuilt_content = self.wd.front.get_blob("0b4e7a0e5fe84ad35fb5f95b9ceeac79").read()
        self.assertEquals(md5sum(rebuilt_content), "0b4e7a0e5fe84ad35fb5f95b9ceeac79")

    def testDeduplicationWithinCommit(self):
        blob_a = self.addWorkdirFile("a.txt", "aaaX")
        blob_b = self.addWorkdirFile("b.txt", "aaaY")
        self.wd.checkin()
        recipe = self.repo.get_recipe(blob_a)
        self.assertTrue(self.repo.get_recipe(blob_a) or self.repo.get_recipe(blob_b))

    def testThatNonalignedEndingsAreDeduplicated(self):
        self.addWorkdirFile("a.txt", "aaab")
        self.wd.checkin()
        blob = self.addWorkdirFile("b.txt", "Xaaab")
        self.wd.checkin()
        recipe = self.repo.get_recipe(blob)
        self.assertEquals(len(recipe['pieces']), 2)
        rebuilt_content = self.wd.front.get_blob("1446f760b3a89d261a13d8b37c20ef11").read()
        self.assertEquals(md5sum(rebuilt_content), "1446f760b3a89d261a13d8b37c20ef11")

    def testTailMatchTooShort(self):
        self.addWorkdirFile("a.txt", "aaab")
        self.wd.checkin()
        blob = self.addWorkdirFile("b.txt", "Xaaabb")
        self.wd.checkin()
        recipe = self.repo.get_recipe(blob)
        self.assertEquals(len(recipe['pieces']), 3)

    def testTailMatchFalsePositive(self):
        self.addWorkdirFile("a.txt", "aaabc")
        self.wd.checkin()
        blob = self.addWorkdirFile("b.txt", "Xaaabb")
        self.wd.checkin()
        recipe = self.repo.get_recipe(blob)
        rebuilt_content = self.wd.front.get_blob("acd3e6fdfcd9e03e3f941c0ed516be81").read()
        self.assertEquals(md5sum(rebuilt_content), "acd3e6fdfcd9e03e3f941c0ed516be81")

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
        self.assertEquals(recipe['pieces'][0], {
                'source': a_blob, 
                'repeat': 1, 'original': False, 'offset': 0, 'size': 3})
        self.assertEquals(recipe['pieces'][1], {
                'source': b_blob, 
                'repeat': 1, 'original': False, 'offset': 0, 'size': 3})
        rebuilt_content = self.wd.front.get_blob(c_blob).read()
        self.assertEquals(md5sum(rebuilt_content), "6547436690a26a399603a7096e876a2d")

    def testInterleavedHit1(self):
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

    def testInterleavedHit2(self):
        a_blob = self.addWorkdirFile("a.txt", "aaa")
        self.wd.checkin()
        b_blob = self.addWorkdirFile("b.txt", "aaaXaaa")
        self.wd.checkin()
        x_blob = md5sum("X")
        recipe = self.repo.get_recipe(b_blob)
        #print_recipe(recipe)
        self.assertEquals(len(recipe['pieces']), 3)
        self.assertEquals(recipe['pieces'][0], {
                'source': a_blob, 
                'repeat': 1, 'original': False, 'offset': 0, 'size': 3})
        self.assertEquals(recipe['pieces'][1], {
                'source': x_blob, 
                'repeat': 1, 'original': True, 'offset': 0, 'size': 1})
        self.assertEquals(recipe['pieces'][2], {
                'source': a_blob, 
                'repeat': 1, 'original': False, 'offset': 0, 'size': 3})
        rebuilt_content = self.wd.front.get_blob(b_blob).read()
        self.assertEquals(md5sum(rebuilt_content), "78c011eeafaad0783eb1d90392e08b46")

    def testAmbigousHit(self):
        a_blob = self.addWorkdirFile("a.txt", "aaaaaa")
        self.wd.checkin()
        b_blob = self.addWorkdirFile("b.txt", "aaa")
        self.wd.checkin()
        recipe = self.repo.get_recipe(b_blob)
        self.assertEquals(len(recipe['pieces']), 1)
        self.assertEquals(recipe['pieces'][0], {
                'source': a_blob,
                'repeat': 1, 'original': False, 'offset': 0, 'size': 3})
        rebuilt_content = self.wd.front.get_blob(b_blob).read()
        self.assertEquals(rebuilt_content, "aaa")
        #print_recipe(recipe)
 
    def testRepeatedHit(self):
        a_blob = self.addWorkdirFile("a.txt", "aaa")
        self.wd.checkin()
        b_blob = self.addWorkdirFile("b.txt", "XXXaaaXXXaaaXXX")
        self.wd.checkin()
        x_blob = md5sum("X")
        recipe = self.repo.get_recipe(b_blob)
        #print_recipe(recipe)

    def testSameRecipeTwice(self):
        a_blob = self.addWorkdirFile("a.txt", "aaa")
        self.wd.checkin()
        b_blob = self.addWorkdirFile("b.txt", "aaaccc")
        c_blob = self.addWorkdirFile("c.txt", "aaaccc")
        self.wd.checkin()
        #print_recipe(recipe)

    def testEmptyFile(self):
        a_blob = self.addWorkdirFile("empty.txt", "")
        self.wd.checkin()
        self.assertTrue("d41d8cd98f00b204e9800998ecf8427e" in self.wd.get_front().get_all_raw_blobs())
        #print_recipe(recipe)

    def testPartialRecipeReads(self):
        a_blob = self.addWorkdirFile("a.txt", "aaa")
        self.wd.checkin()
        #                                      000000000011
        #                                      012345678901
        b_blob = self.addWorkdirFile("b.txt", "XaaaYaaaZaaa")
        self.wd.checkin()
        recipe = self.repo.get_recipe(b_blob)
        self.assertEquals(len(recipe['pieces']), 6)

        self.assertEquals(self.wd.front.get_blob(b_blob, 0, 12).read(), "XaaaYaaaZaaa")
        self.assertEquals(self.wd.front.get_blob(b_blob, 0, 1).read(), "X")
        self.assertEquals(self.wd.front.get_blob(b_blob, 0, 3).read(), "Xaa")
        self.assertEquals(self.wd.front.get_blob(b_blob, 0, 5).read(), "XaaaY")
        self.assertEquals(self.wd.front.get_blob(b_blob, 8, 3).read(), "Zaa")
        self.assertEquals(self.wd.front.get_blob(b_blob, 0, 1).read(), "X")
        self.assertEquals(self.wd.front.get_blob(b_blob, 8, 1).read(), "Z")
        self.assertEquals(self.wd.front.get_blob(b_blob, 7, 2).read(), "aZ")
        self.assertEquals(self.wd.front.get_blob(b_blob, 0).read(), "XaaaYaaaZaaa")
        self.assertEquals(self.wd.front.get_blob(b_blob, 4).read(), "YaaaZaaa")
        self.assertEquals(self.wd.front.get_blob(b_blob, 12).read(), "")
        self.assertEquals(self.wd.front.get_blob(b_blob).read(), "XaaaYaaaZaaa")

        reader = self.wd.front.get_blob(b_blob, 0, 12)
        for c in "XaaaYaaaZaaa":
            self.assertEquals(c, reader.read(1))
        self.assertEquals(reader.read(1), "");

        reader = self.wd.front.get_blob(b_blob, 0, 12)
        for cc in "Xa", "aa", "Ya", "aa", "Za", "aa":
            self.assertEquals(cc, reader.read(2))
        self.assertEquals(reader.read(2), "");

        reader = self.wd.front.get_blob(b_blob, 0, 12)
        for ccc in "Xaa", "aYa", "aaZ", "aaa":
            self.assertEquals(ccc, reader.read(3))
        self.assertEquals(reader.read(3), "");

        reader = self.wd.front.get_blob(b_blob, 0, 12)
        for ccccc in "XaaaY", "aaaZa", "aa":
            self.assertEquals(ccccc, reader.read(5))
        self.assertEquals(reader.read(5), "");

        reader = self.wd.front.get_blob(b_blob, 4)
        for cc in "Ya", "aa", "Za", "aa":
            self.assertEquals(cc, reader.read(2))
        self.assertEquals(reader.read(2), "");
            


    def tearDown(self):
        verify_repo(self.wd.get_front())
        self.assertFalse(self.wd.get_front().repo.get_orphan_blobs())
        for d in self.remove_at_teardown:
            shutil.rmtree(d, ignore_errors = True)

class TestBlockLocationsDB(unittest.TestCase, WorkdirHelper):
    def setUp(self):
        self.remove_at_teardown = []
        self.workdir = self.createTmpName()
        os.mkdir(self.workdir)
        self.dbfile = os.path.join(self.workdir, "database.sqlite")
        self.db = BlocksDB(self.dbfile, 2**16)

    def testRollingEmpty(self):
        self.assertEquals(self.db.get_all_rolling(), [])

    def testRollingSimple(self):
        self.db.begin()
        self.db.add_rolling(17)
        self.db.commit()
        self.assertEquals(self.db.get_all_rolling(), [17])

    def testRollingDuplicate(self):
        self.db.begin()
        self.db.add_rolling(17)
        self.db.add_rolling(17)
        self.db.commit()
        self.assertEquals(self.db.get_all_rolling(), [17])

    def testRollingRange(self):
        self.db.begin()
        self.db.add_rolling(0)
        self.db.add_rolling(2**64 - 1)
        self.db.commit()
        self.assertEquals(set(self.db.get_all_rolling()), set([0, 2**64 - 1]))
        self.db.begin()
        self.assertRaises(OverflowError, self.db.add_rolling, -1)
        self.assertRaises(OverflowError, self.db.add_rolling, 2**64)

    def testBlockSimple(self):
        # blob, offset, md5
        self.db.begin()
        self.db.add_block("d41d8cd98f00b204e9800998ecf8427e", 0, "00000000000000000000000000000000")
        self.db.commit()
        self.assertEquals(list(self.db.get_block_locations("00000000000000000000000000000000")),
                          [("d41d8cd98f00b204e9800998ecf8427e", 0)])

    def testBlockDuplicate(self):
        # blob, offset, md5
        self.db.begin()
        self.db.add_block("d41d8cd98f00b204e9800998ecf8427e", 0, "00000000000000000000000000000000")
        self.db.add_block("d41d8cd98f00b204e9800998ecf8427e", 0, "00000000000000000000000000000000")
        self.db.commit()
        self.assertEquals(list(self.db.get_block_locations("00000000000000000000000000000000")),
                          [("d41d8cd98f00b204e9800998ecf8427e", 0)])

    def tearDown(self):
        for d in self.remove_at_teardown:
            shutil.rmtree(d, ignore_errors = True)


if __name__ == '__main__':
    unittest.main()
