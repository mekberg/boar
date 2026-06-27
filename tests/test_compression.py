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

"""Tests for the blob compression feature: a repository may store all
blob data compressed with a chosen algorithm, described by a "compress"
recipe."""

import sys, os, unittest, shutil, random

if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import workdir
import compression
import deduplication
from blobrepo import repository, blobreader
from common import md5sum, DevNull
from boar_exceptions import UserError, CorruptionError
from front import Front, verify_repo
from wdtools import WorkdirHelper

AVAILABLE = [a for a in compression.KNOWN_ALGORITHMS if compression.is_available(a)]


def deterministic_bytes(n, seed=0):
    rnd = random.Random(seed)
    return bytes(rnd.randrange(256) for _ in range(n))


class TestCodecs(unittest.TestCase):
    """The codec layer on its own: stream compress, then stream
    decompress through the same pump loop CompressReader uses."""

    DATASETS = {
        "empty": b"",
        "tiny": b"x",
        "text": b"the quick brown fox\n" * 3000,
        "zeros": b"\x00" * 200000,
        "random": deterministic_bytes(150000, seed=99),
        "blocksize": deterministic_bytes(65536, seed=7),
    }

    def _compress(self, algo, data, chunk=4096):
        c = compression.get_codec(algo).compressor()
        out = b"".join(c.compress(data[i:i + chunk]) for i in range(0, len(data), chunk))
        return out + c.flush()

    def _decompress(self, algo, comp, in_chunk=1024, out_chunk=1000):
        d = compression.get_codec(algo).decompressor()
        out = b""
        pos = 0
        while True:
            if d.needs_input:
                if pos >= len(comp):
                    break
                feed = comp[pos:pos + in_chunk]
                pos += len(feed)
            else:
                feed = b""
            out += d.decompress(feed, out_chunk)
            if d.eof:
                break
        return out

    def testRoundtrips(self):
        for algo in AVAILABLE:
            for name, data in self.DATASETS.items():
                comp = self._compress(algo, data)
                back = self._decompress(algo, comp)
                self.assertEqual(back, data, "%s/%s roundtrip failed" % (algo, name))

    def testUnknownAlgorithmRejected(self):
        self.assertRaises(UserError, compression.get_codec, "nonsense")

    def testAliases(self):
        self.assertEqual(compression.canonical_name("gz"), "gzip")
        self.assertEqual(compression.canonical_name("LZMA"), "xz")
        self.assertEqual(compression.canonical_name("bzip2"), "bz2")


class TestCompressReader(unittest.TestCase, WorkdirHelper):
    def setUp(self):
        self.remove_at_teardown = []
        self.tmp = self.createTmpName()
        os.mkdir(self.tmp)

    def tearDown(self):
        for path in self.remove_at_teardown:
            if os.path.exists(path):
                shutil.rmtree(path, ignore_errors=True)

    class _FakeRepo(object):
        def __init__(self, blobdir):
            self.blobdir = blobdir

        def get_blob_path(self, blob):
            return os.path.join(self.blobdir, blob)

    def _make_recipe(self, algo, data, split=None):
        c = compression.get_codec(algo).compressor()
        comp = b"".join(c.compress(data[i:i + 4096]) for i in range(0, len(data), 4096)) + c.flush()
        if split is None:
            split = max(len(comp), 1)
        pieces = []
        for i in range(0, max(len(comp), 1), split):
            chunk = comp[i:i + split]
            if not chunk and i > 0:
                break
            name = md5sum(chunk)
            with open(os.path.join(self.tmp, name), "wb") as f:
                f.write(chunk)
            pieces.append({"source": name, "offset": 0, "size": len(chunk)})
        return {"method": "compress", "algorithm": algo, "md5sum": md5sum(data),
                "size": len(data), "pieces": pieces}

    def testFullAndRandomAccess(self):
        repo = self._FakeRepo(self.tmp)
        for algo in AVAILABLE:
            data = deterministic_bytes(120000, seed=3) + b"tail"
            for split in (None, 4096):
                recipe = self._make_recipe(algo, data, split)
                # full streaming read
                r = blobreader.CompressReader(recipe, repo)
                full = b""
                while r.bytes_left():
                    full += r.read(777)
                self.assertEqual(full, data, "%s split=%s full read" % (algo, split))
                # random access
                for off, size in [(0, 5), (len(data) // 2, 100), (len(data) - 3, 3), (10, len(data) - 10)]:
                    rr = blobreader.CompressReader(recipe, repo, offset=off, size=size)
                    got = b""
                    while rr.bytes_left():
                        got += rr.read(64)
                    self.assertEqual(got, data[off:off + size], "%s split=%s [%s:%s]" % (algo, split, off, off + size))


class TestRepoConfig(unittest.TestCase, WorkdirHelper):
    def setUp(self):
        self.remove_at_teardown = []

    def tearDown(self):
        for path in self.remove_at_teardown:
            if os.path.exists(path):
                shutil.rmtree(path, ignore_errors=True)

    def testDefaultIsNone(self):
        repopath = self.createTmpName()
        repository.create_repository(repopath)
        self.assertEqual(repository.Repo(repopath).get_compression(), None)

    def testStoredCanonical(self):
        repopath = self.createTmpName()
        repository.create_repository(repopath, compression_algorithm="gz")  # alias
        self.assertEqual(repository.Repo(repopath).get_compression(), "gzip")
        stats = dict(repository.Repo(repopath).get_stats())
        self.assertEqual(stats["compression"], "gzip")

    def testUnknownAlgorithmRejected(self):
        repopath = self.createTmpName()
        self.assertRaises(UserError, repository.create_repository,
                          repopath, compression_algorithm="nope")
        self.assertFalse(os.path.exists(repopath))


class _CompressionWorkdirBase(unittest.TestCase, WorkdirHelper):
    algorithm = "gzip"
    max_blob_size = None
    enable_deduplication = False

    def setUp(self):
        self.remove_at_teardown = []
        self.workdir = self.createTmpName()
        self.repopath = self.createTmpName()
        repository.create_repository(self.repopath,
                                     enable_deduplication=self.enable_deduplication,
                                     max_blob_size=self.max_blob_size,
                                     compression_algorithm=self.algorithm)
        os.mkdir(self.workdir)
        self.wd = workdir.Workdir(self.repopath, u"TestSession", u"", None, self.workdir)
        self.wd.setLogOutput(DevNull())
        self.wd.use_progress_printer(False)
        self.repo = self.wd.front.repo
        self.wd.get_front().mksession(u"TestSession")

    def tearDown(self):
        for path in self.remove_at_teardown:
            if os.path.exists(path):
                shutil.rmtree(path, ignore_errors=True)

    def assert_roundtrip(self, md5, expected):
        data = self.wd.front.get_blob(md5).read()
        self.assertEqual(md5sum(data), md5)
        self.assertEqual(data, expected)


def _make_algorithm_case(algo):
    class _Case(_CompressionWorkdirBase):
        algorithm = algo

        def testCompressedCommitRoundtrips(self):
            text = b"highly compressible payload " * 8000
            rnd = deterministic_bytes(120000, seed=5)
            md5_text = self.addWorkdirFile("text.bin", text)
            md5_rnd = self.addWorkdirFile("rand.bin", rnd)
            md5_empty = self.addWorkdirFile("empty.bin", b"")
            self.wd.checkin()

            for md5 in (md5_text, md5_rnd, md5_empty):
                self.assertTrue(self.repo.has_recipe_blob(md5))
                self.assertFalse(self.repo.has_raw_blob(md5))
                recipe = self.repo.get_recipe(md5)
                self.assertEqual(recipe["method"], "compress")
                self.assertEqual(recipe["algorithm"], algo)

            # The compressible file must actually be stored smaller.
            recipe = self.repo.get_recipe(md5_text)
            stored = sum(os.path.getsize(self.repo.get_blob_path(p["source"])) for p in recipe["pieces"])
            self.assertTrue(stored < len(text))

            self.assert_roundtrip(md5_text, text)
            self.assert_roundtrip(md5_rnd, rnd)
            self.assert_roundtrip(md5_empty, b"")
            self.assertTrue(verify_repo(self.wd.front, verbose=False))

    _Case.__name__ = "TestCompress_" + algo
    _Case.__qualname__ = _Case.__name__
    return _Case


# Generate one test class per available algorithm.
_thismodule = sys.modules[__name__]
for _algo in AVAILABLE:
    setattr(_thismodule, "TestCompress_" + _algo, _make_algorithm_case(_algo))


class TestCompressionWithMaxBlobSize(_CompressionWorkdirBase):
    algorithm = "gzip"
    max_blob_size = 65536

    def testCompressedStreamIsSplit(self):
        # Incompressible data => compressed size ~ original => must split.
        data = deterministic_bytes(300000, seed=8)
        md5 = self.addWorkdirFile("big.bin", data)
        self.wd.checkin()
        self.assertTrue(self.repo.has_recipe_blob(md5))
        recipe = self.repo.get_recipe(md5)
        self.assertTrue(len(recipe["pieces"]) > 1, "expected the compressed stream to be split")
        for name in self.repo.get_raw_blob_names():
            self.assertTrue(os.path.getsize(self.repo.get_blob_path(name)) <= self.max_blob_size)
        self.assert_roundtrip(md5, data)
        self.assertTrue(verify_repo(self.wd.front, verbose=False))


class TestTruncationRaises(unittest.TestCase, WorkdirHelper):
    """A sub-blob that is shorter on disk than its recipe claims must raise
    CorruptionError, not spin forever (regression for the streaming reader)."""

    def setUp(self):
        self.remove_at_teardown = []
        self.tmp = self.createTmpName()
        os.mkdir(self.tmp)

    def tearDown(self):
        for path in self.remove_at_teardown:
            if os.path.exists(path):
                shutil.rmtree(path, ignore_errors=True)

    class _FakeRepo(object):
        def __init__(self, blobdir):
            self.blobdir = blobdir

        def get_blob_path(self, blob):
            return os.path.join(self.blobdir, blob)

    def _write(self, data):
        name = md5sum(data)
        with open(os.path.join(self.tmp, name), "wb") as f:
            f.write(data)
        return name

    def testConcatRecipeTruncatedSubBlob(self):
        # A plain concat recipe (as produced by --max-file-size) with a
        # source blob that is shorter than the recipe declares.
        name = self._write(b"only-ten!!")  # 10 bytes on disk
        recipe = {"method": "concat", "md5sum": "0" * 32, "size": 20,
                  "pieces": [{"source": name, "offset": 0, "size": 20, "repeat": 1}]}
        reader = blobreader.RecipeReader(recipe, self._FakeRepo(self.tmp))
        self.assertRaises(CorruptionError, reader.read)

    def testCompressTruncatedSubBlob(self):
        algo = "gzip"
        data = b"some compressible data " * 1000
        c = compression.get_codec(algo).compressor()
        comp = c.compress(data) + c.flush()
        name = self._write(comp[:len(comp) // 2])  # truncate the compressed blob on disk
        recipe = {"method": "compress", "algorithm": algo, "md5sum": md5sum(data),
                  "size": len(data),
                  "pieces": [{"source": name, "offset": 0, "size": len(comp)}]}
        reader = blobreader.CompressReader(recipe, self._FakeRepo(self.tmp))
        # Either a decompressor error or our truncation guard - but it must
        # raise quickly, not hang.
        self.assertRaises(Exception, lambda: b"".join(iter(lambda: reader.read(4096) or None, None)))


class TestSubBlobNameCollision(_CompressionWorkdirBase):
    """A file whose content equals boar's compressed representation of
    another file shares an md5 between a raw sub-blob and a recipe. The
    commit must reconcile this instead of aborting."""
    algorithm = "gzip"

    def testCollidingCommitSucceeds(self):
        payload = b"highly compressible payload " * 50
        c = compression.get_codec(self.algorithm).compressor()
        compressed = c.compress(payload) + c.flush()
        self.assertNotEqual(md5sum(compressed), md5sum(payload))
        # "a_..." sorts before "z_...", so the file whose content is the
        # compressed form is uploaded first (writes a recipe named
        # md5(compressed)); the payload file is uploaded second (writes a
        # raw sub-blob of the same name).
        md5_compressed_file = self.addWorkdirFile("a_compressed.bin", compressed)
        md5_payload_file = self.addWorkdirFile("z_payload.bin", payload)
        self.assertEqual(md5_compressed_file, md5sum(compressed))
        self.wd.checkin()  # must not raise
        self.assert_roundtrip(md5_compressed_file, compressed)
        self.assert_roundtrip(md5_payload_file, payload)
        self.assertTrue(verify_repo(self.wd.front, verbose=False))


@unittest.skipUnless(deduplication.dedup_available, "deduplication module not installed")
class TestCompressionWinsOverDedup(_CompressionWorkdirBase):
    algorithm = "gzip"
    enable_deduplication = True

    def testCompressionTakesPrecedence(self):
        data = b"repeated block of bytes " * 5000
        md5 = self.addWorkdirFile("a.bin", data)
        self.wd.checkin()
        recipe = self.repo.get_recipe(md5)
        self.assertEqual(recipe["method"], "compress")
        self.assert_roundtrip(md5, data)
        self.assertTrue(verify_repo(self.wd.front, verbose=False))


if __name__ == '__main__':
    print("Available compression algorithms:", AVAILABLE)
    unittest.main()
