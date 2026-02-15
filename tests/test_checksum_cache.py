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

"""
Tests for ChecksumCache, specifically verifying that row checksums
are calculated compatible with Python 2.7's float-to-string behavior.

Python 2.7's str(float) uses 12 significant digits (like '%.12g')
while Python 3's str(float) uses full precision. Old workdir caches
created with Python 2.7 must remain readable by modern Python.
"""

import sys, os, unittest, sqlite3, hashlib

if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from workdir import ChecksumCache
from common import md5sum


def python27_row_md5(path, mtime, md5):
    """Compute the row checksum exactly as Python 2.7 would have.

    Python 2.7 str(float) is equivalent to '%.12g' formatting, with
    the addition that integer-valued floats always include '.0'
    (e.g. '1234567890.0' instead of '1234567890').
    """
    s = '%.12g' % mtime
    if '.' not in s and 'e' not in s and 'E' not in s:
        s += '.0'
    return md5sum(path.encode("utf8") + b"!" + s.encode("utf8") + b"!" + md5.encode("utf8"))


class TestChecksumCachePy27Compat(unittest.TestCase):
    """Verify that ChecksumCache produces and accepts checksums
    compatible with Python 2.7's float formatting."""

    def test_cache_set_get_with_precise_mtime(self):
        """A cache entry with a high-precision mtime (more than 12
        significant digits) must round-trip correctly through set/get."""
        cache = ChecksumCache(":memory:")
        path = "some/file.txt"
        mtime = 1234567890.123456  # 16 sig digits - differs between py2/py3
        md5 = "d41d8cd98f00b204e9800998ecf8427e"
        cache.set(path, mtime, md5)
        result = cache.get(path, mtime)
        self.assertEqual(result, md5)

    def test_cache_accepts_python27_checksums(self):
        """A cache database written by Python 2.7 must be readable.

        We simulate this by directly inserting a row with a checksum
        computed using Python 2.7's str(float) formatting."""
        cache = ChecksumCache(":memory:")
        path = "some/file.txt"
        mtime = 1234567890.123456
        md5 = "d41d8cd98f00b204e9800998ecf8427e"

        # Compute row checksum the way Python 2.7 would have
        row_md5 = python27_row_md5(path, mtime, md5)

        # Directly insert the row as if Python 2.7 had written it
        cache.conn.execute(
            "REPLACE INTO ccache (path, mtime, md5, row_md5) VALUES (?, ?, ?, ?)",
            (path, mtime, md5, row_md5)
        )

        # Reading it back must succeed (not raise "cache corrupted")
        result = cache.get(path, mtime)
        self.assertEqual(result, md5)

    def test_cache_accepts_python27_checksums_various_mtimes(self):
        """Test several mtime values that produce different strings
        in Python 2.7 vs Python 3."""
        cache = ChecksumCache(":memory:")
        md5 = "d41d8cd98f00b204e9800998ecf8427e"

        test_cases = [
            ("file1.txt", 1234567890.123456),   # truncated in py2.7
            ("file2.txt", 1609459200.123),       # truncated in py2.7
            ("file3.txt", 123.456789012345),     # truncated in py2.7
            ("file4.txt", 1234567890.0),         # same in both
            ("file5.txt", 1234567890.5),         # same in both
            ("file6.txt", 0.1),                  # same in both
        ]

        for path, mtime in test_cases:
            row_md5 = python27_row_md5(path, mtime, md5)
            cache.conn.execute(
                "REPLACE INTO ccache (path, mtime, md5, row_md5) VALUES (?, ?, ?, ?)",
                (path, mtime, md5, row_md5)
            )
            with self.subTest(path=path, mtime=mtime):
                result = cache.get(path, mtime)
                self.assertEqual(result, md5,
                    f"Failed to read Python 2.7 cache entry for mtime={mtime}")

    def test_newly_written_entries_readable(self):
        """Entries written by the current code must also be readable."""
        cache = ChecksumCache(":memory:")
        path = "another/file.txt"
        mtime = 1609459200.123456
        md5 = "abc123def456abc123def456abc123de"
        cache.set(path, mtime, md5)
        result = cache.get(path, mtime)
        self.assertEqual(result, md5)

    def test_newly_written_entries_use_py27_format(self):
        """New entries should use Python 2.7-compatible checksums so
        that the cache format is consistent regardless of Python version."""
        cache = ChecksumCache(":memory:")
        path = "test/file.txt"
        mtime = 1234567890.123456
        md5 = "d41d8cd98f00b204e9800998ecf8427e"
        cache.set(path, mtime, md5)

        # Read back the raw row_md5 from the database
        c = cache.conn.cursor()
        c.execute("SELECT row_md5 FROM ccache WHERE path = ? AND mtime = ?", (path, mtime))
        stored_row_md5 = c.fetchone()[0]

        # It should match the Python 2.7 computation
        expected = python27_row_md5(path, mtime, md5)
        self.assertEqual(stored_row_md5, expected,
            "New cache entries should use Python 2.7-compatible row checksums")


if __name__ == '__main__':
    unittest.main()
