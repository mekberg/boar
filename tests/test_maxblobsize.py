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

"""Tests for the per-repository maximum blob size feature, which
splits oversized files into several smaller blobs tied together with a
recipe."""

import sys, os, unittest

if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import workdir
from blobrepo import repository
from common import md5sum, DevNull, parse_human_size
from boar_exceptions import UserError
from front import Front, verify_repo
from deduplication import dedup_available
from wdtools import WorkdirHelper


def deterministic_bytes(n, seed=0):
    """Return n bytes of deterministic, hard-to-compress data."""
    return bytes(((i * 2654435761 + seed * 40503 + 7) % 251) for i in range(n))


class TestParseHumanSize(unittest.TestCase):
    def testPlainInteger(self):
        self.assertEqual(parse_human_size("0"), 0)
        self.assertEqual(parse_human_size("65536"), 65536)
        self.assertEqual(parse_human_size(" 100 "), 100)

    def testSuffixes(self):
        self.assertEqual(parse_human_size("1k"), 1024)
        self.assertEqual(parse_human_size("1K"), 1024)
        self.assertEqual(parse_human_size("2M"), 2 * 1024 ** 2)
        self.assertEqual(parse_human_size("3g"), 3 * 1024 ** 3)
        self.assertEqual(parse_human_size("1T"), 1024 ** 4)

    def testByteMarker(self):
        self.assertEqual(parse_human_size("100b"), 100)
        self.assertEqual(parse_human_size("5MB"), 5 * 1024 ** 2)
        self.assertEqual(parse_human_size("5mb"), 5 * 1024 ** 2)

    def testFractional(self):
        self.assertEqual(parse_human_size("1.5k"), 1536)

    def testMalformed(self):
        for bad in ("", "   ", "abc", "1.2.3", "k", "M", "-5", "-1k", "5x",
                    "inf", "infinity", "infg", "nan", "9" * 400):
            self.assertRaises(ValueError, parse_human_size, bad)


class TestRepoConfig(unittest.TestCase, WorkdirHelper):
    def setUp(self):
        self.remove_at_teardown = []

    def tearDown(self):
        import shutil
        for path in self.remove_at_teardown:
            if os.path.exists(path):
                shutil.rmtree(path, ignore_errors=True)

    def testDefaultIsNone(self):
        repopath = self.createTmpName()
        repository.create_repository(repopath)
        repo = repository.Repo(repopath)
        self.assertEqual(repo.get_max_blob_size(), None)

    def testStoredAndRead(self):
        repopath = self.createTmpName()
        repository.create_repository(repopath, max_blob_size=131072)
        self.assertTrue(os.path.exists(os.path.join(repopath, repository.MAXBLOBSIZE_FILE)))
        repo = repository.Repo(repopath)
        self.assertEqual(repo.get_max_blob_size(), 131072)
        # Make sure it is reported in the repo statistics too.
        stats = dict(repo.get_stats())
        self.assertEqual(stats["max_blob_size"], 131072)

    def testBelowMinimumRejected(self):
        repopath = self.createTmpName()
        self.assertRaises(UserError, repository.create_repository,
                          repopath, max_blob_size=repository.MIN_MAX_BLOB_SIZE - 1)
        self.assertFalse(os.path.exists(repopath))

    def testCorruptConfigRaisesCorruptionError(self):
        from boar_exceptions import CorruptionError
        repopath = self.createTmpName()
        repository.create_repository(repopath, max_blob_size=131072)
        with open(os.path.join(repopath, repository.MAXBLOBSIZE_FILE), "wb") as f:
            f.write(b"not-a-number")
        repo = repository.Repo(repopath)
        self.assertRaises(CorruptionError, repo.get_max_blob_size)


class _SplitTestBase(unittest.TestCase, WorkdirHelper):
    enable_deduplication = False

    def setUp(self):
        self.remove_at_teardown = []
        self.workdir = self.createTmpName()
        self.repopath = self.createTmpName()
        self.max_blob_size = 65536
        repository.create_repository(self.repopath,
                                     enable_deduplication=self.enable_deduplication,
                                     max_blob_size=self.max_blob_size)
        os.mkdir(self.workdir)
        self.wd = workdir.Workdir(self.repopath, u"TestSession", u"", None, self.workdir)
        self.wd.setLogOutput(DevNull())
        self.wd.use_progress_printer(False)
        self.repo = self.wd.front.repo
        self.wd.get_front().mksession(u"TestSession")

    def tearDown(self):
        import shutil
        for path in self.remove_at_teardown:
            if os.path.exists(path):
                shutil.rmtree(path, ignore_errors=True)

    def assert_blob_size_invariant(self):
        """No raw blob in the repository may exceed the configured limit."""
        for name in self.repo.get_raw_blob_names():
            size = os.path.getsize(self.repo.get_blob_path(name))
            self.assertTrue(size <= self.max_blob_size,
                            "Raw blob %s has size %s > limit %s" % (name, size, self.max_blob_size))

    def assert_roundtrip(self, md5, expected_content):
        reader = self.wd.front.get_blob(md5)
        data = reader.read()
        self.assertEqual(len(data), len(expected_content))
        self.assertEqual(md5sum(data), md5)
        self.assertEqual(data, expected_content)


class TestSplitNoDedup(_SplitTestBase):
    enable_deduplication = False

    def testFileLargerThanLimitGetsRecipe(self):
        content = deterministic_bytes(350000, seed=1)  # not a multiple of the limit
        md5 = self.addWorkdirFile("big.bin", content)
        self.wd.checkin()
        # The file must be represented by a recipe, not a single raw blob.
        self.assertTrue(self.repo.has_recipe_blob(md5))
        self.assertFalse(self.repo.has_raw_blob(md5))
        recipe = self.repo.get_recipe(md5)
        self.assertEqual(recipe["size"], len(content))
        self.assertEqual(sum(p["size"] * p["repeat"] for p in recipe["pieces"]), len(content))
        self.assert_blob_size_invariant()
        self.assert_roundtrip(md5, content)
        self.assertTrue(verify_repo(self.wd.front, verbose=False))

    def testFileAtAndBelowLimitStaysRaw(self):
        exact = deterministic_bytes(self.max_blob_size, seed=2)
        small = deterministic_bytes(1000, seed=3)
        md5_exact = self.addWorkdirFile("exact.bin", exact)
        md5_small = self.addWorkdirFile("small.bin", small)
        self.wd.checkin()
        for md5 in (md5_exact, md5_small):
            self.assertTrue(self.repo.has_raw_blob(md5))
            self.assertFalse(self.repo.has_recipe_blob(md5))
        self.assert_blob_size_invariant()
        self.assert_roundtrip(md5_exact, exact)
        self.assert_roundtrip(md5_small, small)

    def testEmptyFile(self):
        md5 = self.addWorkdirFile("empty.bin", b"")
        self.wd.checkin()
        self.assertEqual(md5, "d41d8cd98f00b204e9800998ecf8427e")
        self.assertTrue(self.repo.has_raw_blob(md5))
        self.assertFalse(self.repo.has_recipe_blob(md5))
        self.assert_roundtrip(md5, b"")
        self.assertTrue(verify_repo(self.wd.front, verbose=False))

    def testIdenticalLargeFilesShareSubBlobs(self):
        content = deterministic_bytes(200000, seed=4)
        self.addWorkdirFile("a.bin", content)
        self.addWorkdirFile("b.bin", content)
        self.wd.checkin()
        # Two identical files share the same recipe and the same set of
        # sub-blobs, so the raw blob count is exactly the number of
        # chunks of a single file.
        expected_chunks = (len(content) + self.max_blob_size - 1) // self.max_blob_size
        self.assertEqual(len(self.repo.get_raw_blob_names()), expected_chunks)
        self.assertEqual(len(self.repo.get_recipe_names()), 1)
        self.assert_blob_size_invariant()
        self.assertTrue(verify_repo(self.wd.front, verbose=False))


@unittest.skipUnless(dedup_available, "deduplication module not installed")
class TestSplitWithDedup(_SplitTestBase):
    enable_deduplication = True

    def testDedupAcrossSplitBoundaries(self):
        base = deterministic_bytes(300000, seed=5)
        md5_a = self.addWorkdirFile("a.bin", base)
        self.wd.checkin()
        raw_after_first = len(self.repo.get_raw_blob_names())

        # A second file that contains the same large body with a small
        # prefix. Block deduplication should recognise the shared body
        # even though it is stored split across several sub-blobs, so
        # only a small amount of new raw data is added.
        b_content = b"A short unique prefix.\n" + base
        md5_b = self.addWorkdirFile("b.bin", b_content)
        self.wd.checkin()
        raw_after_second = len(self.repo.get_raw_blob_names())

        self.assertTrue(self.repo.has_recipe_blob(md5_b))
        recipe_b = self.repo.get_recipe(md5_b)
        self.assertTrue(any(not p["original"] for p in recipe_b["pieces"]),
                        "Expected deduplicated (non-original) pieces in the recipe")
        # Far fewer new blobs than a naive re-split would require.
        self.assertTrue(raw_after_second - raw_after_first <= 2,
                        "Too many new raw blobs: %s -> %s" % (raw_after_first, raw_after_second))
        self.assert_blob_size_invariant()
        self.assert_roundtrip(md5_a, base)
        self.assert_roundtrip(md5_b, b_content)
        self.assertTrue(verify_repo(self.wd.front, verbose=False))


if __name__ == '__main__':
    unittest.main()
