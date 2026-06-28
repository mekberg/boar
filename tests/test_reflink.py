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

"""Tests for "boar clone --reflink", which shares blobs with the source
via copy-on-write reflinks where the destination would store them
verbatim."""

import sys, os, unittest, shutil, tempfile

if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import workdir
import common
import deduplication
from blobrepo import repository
import front as front_module
from front import Front, clone, verify_repo, _local_source_has_raw_blob
from common import md5sum, DevNull
from boar_exceptions import UserError


def find_reflink_dir():
    """Return a base directory on a reflink-capable filesystem, or None."""
    candidates = ["/gigant/tmp", tempfile.gettempdir()]
    for base in candidates:
        if not (base and os.path.isdir(base)):
            continue
        try:
            probe = tempfile.mkdtemp(prefix="boar_reflink_probe_", dir=base)
        except OSError:
            continue
        try:
            src = os.path.join(probe, "src")
            with open(src, "wb") as f:
                f.write(b"probe")
            if common.reflink_supported(src, probe):
                return base
        finally:
            shutil.rmtree(probe, ignore_errors=True)
    return None


REFLINK_DIR = find_reflink_dir()


def _commit_files(repopath, sessionname, files):
    """Create a fresh repo+session and commit the given {name: bytes}."""
    repository.create_repository(repopath)
    wd_path = repopath + "_wd"
    os.mkdir(wd_path)
    wd = workdir.Workdir(repopath, sessionname, u"", None, wd_path)
    wd.setLogOutput(DevNull())
    wd.use_progress_printer(False)
    wd.get_front().mksession(sessionname)
    for name, data in files.items():
        with open(os.path.join(wd_path, name), "wb") as f:
            f.write(data)
    wd.checkin()
    return wd


class TestReflinkPrimitive(unittest.TestCase):
    def setUp(self):
        self.dirs = []

    def tearDown(self):
        for d in self.dirs:
            shutil.rmtree(d, ignore_errors=True)

    def _tmp(self, base):
        d = tempfile.mkdtemp(prefix="boar_reflink_", dir=base)
        self.dirs.append(d)
        return d

    def testUnsupportedReturnsFalseNotRaise(self):
        # On a non-reflink fs this is False, on a reflink fs True - either
        # way it must not raise.
        d1 = self._tmp(tempfile.gettempdir())
        d2 = self._tmp(tempfile.gettempdir())
        src = os.path.join(d1, "src")
        with open(src, "wb") as f:
            f.write(b"x")
        self.assertIn(common.reflink_supported(src, d2), (True, False))

    def testProbeDoesNotWriteToSource(self):
        # The probe must work even when the source side is read-only (it
        # only reads the source file). Simulate by making src_dir read-only.
        src_dir = self._tmp(tempfile.gettempdir())
        dst_dir = self._tmp(tempfile.gettempdir())
        src = os.path.join(src_dir, "src")
        with open(src, "wb") as f:
            f.write(b"x")
        os.chmod(src_dir, 0o500)  # read+execute only, no write
        try:
            # Must not raise and must not need to write into src_dir.
            self.assertIn(common.reflink_supported(src, dst_dir), (True, False))
        finally:
            os.chmod(src_dir, 0o700)

    @unittest.skipUnless(REFLINK_DIR, "no reflink-capable filesystem available")
    def testReflinkCopiesContentAndShares(self):
        d = self._tmp(REFLINK_DIR)
        src = os.path.join(d, "src.bin")
        dst = os.path.join(d, "dst.bin")
        data = os.urandom(1024 * 1024)
        with open(src, "wb") as f:
            f.write(data)
        common.reflink_file(src, dst)
        with open(dst, "rb") as f:
            self.assertEqual(f.read(), data)
        # Reflinking onto an existing destination must fail (EEXIST).
        self.assertRaises(OSError, common.reflink_file, src, dst)


class TestReflinkableDecision(unittest.TestCase):
    """Policy decision - which blobs may be reflinked - independent of the
    actual filesystem (runs anywhere)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="boar_reflink_dec_")
        self.src_repo = os.path.join(self.tmp, "src")
        self.wd = _commit_files(self.src_repo, u"S",
                                {"a.bin": b"x" * 200000, "mid.bin": b"m" * 80000,
                                 "small.bin": b"hi"})
        self.source_front = self.wd.get_front()
        self.bloblist = self.source_front.get_session_bloblist(
            self.source_front.find_last_revision(u"S"))
        self.big = [b for b in self.bloblist if b['filename'] == "a.bin"][0]
        self.mid = [b for b in self.bloblist if b['filename'] == "mid.bin"][0]
        self.small = [b for b in self.bloblist if b['filename'] == "small.bin"][0]

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _dest(self, name, **kwargs):
        path = os.path.join(self.tmp, name)
        repository.create_repository(path, **kwargs)
        return Front(repository.Repo(path))

    # The destination decides whether it would store a blob verbatim (and so
    # may have it reflinked) purely from the blob's size and its own config -
    # see Repository.stores_blob_verbatim().
    def testPlainDestinationIsReflinkable(self):
        dest = self._dest("plain")
        self.assertTrue(dest.repo.stores_blob_verbatim(self.big['size']))
        self.assertTrue(dest.repo.stores_blob_verbatim(self.small['size']))

    @unittest.skipUnless(deduplication.dedup_available, "deduplication module not installed")
    def testDedupDestinationIsNot(self):
        dest = self._dest("dedup", enable_deduplication=True)
        self.assertFalse(dest.repo.stores_blob_verbatim(self.big['size']))

    def testMaxBlobSizeRespected(self):
        dest = self._dest("split", max_blob_size=65536)
        # a.bin (200000) exceeds the limit -> not stored verbatim; small fits.
        self.assertFalse(dest.repo.stores_blob_verbatim(self.big['size']))
        self.assertTrue(dest.repo.stores_blob_verbatim(self.small['size']))

    def testAlignedSplitSizeUsedNotRawMax(self):
        # max_blob_size is not a multiple of the dedup block size (65536),
        # so the real split threshold is the aligned value. mid.bin (80000)
        # is below max but above the aligned split size, so a normal clone
        # would split it - it must NOT be stored verbatim.
        dest = self._dest("split_unaligned", max_blob_size=100000)  # aligned -> 65536
        self.assertEqual(dest.get_blob_split_size(), 65536)
        self.assertFalse(dest.repo.stores_blob_verbatim(self.mid['size']))
        # With a larger limit the aligned split size (196608) leaves mid.bin
        # stored verbatim, so it is reflinkable.
        dest2 = self._dest("split_fits", max_blob_size=200000)  # aligned -> 3*65536
        self.assertEqual(dest2.get_blob_split_size(), 196608)
        self.assertTrue(dest2.repo.stores_blob_verbatim(self.mid['size']))

    # Reflinking additionally requires both repos to be local and the source
    # to hold the blob as a single raw file - see _local_source_has_raw_blob().
    def testRemoteFrontIsNot(self):
        class FakeRemoteFront(object):
            pass
        self.assertFalse(_local_source_has_raw_blob(
            self.source_front, FakeRemoteFront(), self.big['md5sum']))
        self.assertFalse(_local_source_has_raw_blob(
            FakeRemoteFront(), self.source_front, self.big['md5sum']))

    def testLocalSourceWithRawBlobIs(self):
        # Both local and the source stores the blob as a single raw file.
        dest = self._dest("plain_local")
        self.assertTrue(_local_source_has_raw_blob(
            self.source_front, dest, self.big['md5sum']))


@unittest.skipUnless(REFLINK_DIR, "no reflink-capable filesystem available")
class TestReflinkClone(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="boar_reflink_clone_", dir=REFLINK_DIR)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _avail(self):
        s = os.statvfs(self.tmp)
        return s.f_bavail * s.f_frsize

    def _clone(self, src_repo, dst_repo, reflink, **dst_kwargs):
        repository.create_repository(dst_repo, **dst_kwargs)
        source_front = Front(repository.Repo(src_repo))
        target_front = Front(repository.Repo(dst_repo))
        self.last_stats = clone(source_front, target_front, reflink=reflink)
        return target_front

    def testPlainReflinkClone(self):
        src = os.path.join(self.tmp, "src")
        payload = {"a.bin": os.urandom(2 * 1024 * 1024),
                   "b.bin": os.urandom(2 * 1024 * 1024)}
        _commit_files(src, u"S", payload)

        target = self._clone(src, os.path.join(self.tmp, "dst"), reflink=True)

        # Both blobs were reflinked (a successful FICLONE means the data is
        # shared copy-on-write); none were copied.
        self.assertEqual(self.last_stats, {"reflinked": 2, "copied": 0})
        # All blobs present as raw blobs, content correct, repo verifies.
        for name, data in payload.items():
            md5 = md5sum(data)
            self.assertTrue(target.repo.has_raw_blob(md5))
            self.assertEqual(target.get_blob(md5).read(), data)
        self.assertTrue(verify_repo(target, verbose=False))

    @unittest.skipUnless(deduplication.dedup_available, "deduplication module not installed")
    def testDedupDestinationStillDeduplicates(self):
        src = os.path.join(self.tmp, "src")
        base = os.urandom(4 * 1024 * 1024)
        _commit_files(src, u"S", {"a.bin": base, "b.bin": b"PREFIX" + base})

        target = self._clone(src, os.path.join(self.tmp, "dst"), reflink=True,
                             enable_deduplication=True)
        # b.bin must have been deduplicated against a.bin (stored as a
        # recipe), proving reflink did NOT bypass deduplication.
        b_md5 = md5sum(b"PREFIX" + base)
        self.assertTrue(target.repo.has_recipe_blob(b_md5))
        self.assertTrue(verify_repo(target, verbose=False))

    def testReflinkReplaceCleansTempOnFailure(self):
        # If os.replace fails, the original raw blob must stay intact and no
        # orphan temp file may be left (which would later fail verify_meta).
        repo_path = os.path.join(self.tmp, "r")
        repository.create_repository(repo_path)
        repo = repository.Repo(repo_path)
        sw = repo.create_snapshot(u"S")
        try:
            data = os.urandom(100000)
            md5 = md5sum(data)
            src = os.path.join(self.tmp, "src.bin")
            with open(src, "wb") as f:
                f.write(data)
            sw.reflink_new_blob(md5, len(data), src)  # place a raw blob in the snapshot
            orig_replace = os.replace

            def boom(a, b):
                raise OSError("simulated replace failure")
            os.replace = boom
            try:
                self.assertRaises(OSError, sw.reflink_replace_blob, md5, src)
            finally:
                os.replace = orig_replace
            # Original blob still present, identical content; no temp left.
            dest = os.path.join(sw.session_path, md5)
            self.assertTrue(os.path.exists(dest))
            self.assertEqual(md5sum(open(dest, "rb").read()), md5)
            leftover = [f for f in os.listdir(sw.session_path) if f.startswith("reflink_")]
            self.assertEqual(leftover, [])
        finally:
            sw.cancel()

    @unittest.skipUnless(deduplication.dedup_available, "deduplication module not installed")
    def testDedupDestinationReflinksVerbatimBlobs(self):
        # In a deduplicating destination, blobs that find no duplicate
        # blocks are stored verbatim as raw blobs and must be reflinked
        # (shared), while a duplicate is still deduplicated to a recipe.
        src = os.path.join(self.tmp, "src")
        base = os.urandom(2 * 1024 * 1024)
        uniq = os.urandom(2 * 1024 * 1024)
        _commit_files(src, u"S", {"a.bin": base, "b.bin": b"PREFIX" + base, "c.bin": uniq})

        target = self._clone(src, os.path.join(self.tmp, "dst"), reflink=True,
                             enable_deduplication=True)

        # The two unique blobs (a.bin, c.bin) are stored verbatim and shared
        # via reflink; the duplicate (b.bin) is deduplicated, not reflinked.
        self.assertEqual(self.last_stats, {"reflinked": 2, "copied": 1})
        self.assertTrue(target.repo.has_raw_blob(md5sum(base)))
        self.assertTrue(target.repo.has_raw_blob(md5sum(uniq)))
        self.assertEqual(target.get_blob(md5sum(uniq)).read(), uniq)
        # b.bin still deduplicated (reflink did not disable dedup).
        self.assertTrue(target.repo.has_recipe_blob(md5sum(b"PREFIX" + base)))
        self.assertTrue(verify_repo(target, verbose=False))


if __name__ == '__main__':
    print("Reflink-capable test dir:", REFLINK_DIR)
    unittest.main()
