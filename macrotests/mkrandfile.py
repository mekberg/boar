#!/usr/bin/env python3
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

import hashlib
import math
import os
import random
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def md5sum_file(filename: str) -> str:
    m = hashlib.md5()
    with open(filename, "rb") as f:
        for chunk in iter(lambda: f.read(1024), b""):
            m.update(chunk)
    return m.hexdigest()


def to_text(s) -> str:
    if s is None:
        return ""
    return s if isinstance(s, str) else str(s)


def mkrandfile_deterministic(path: str, filesize_bytes: int, seed: int = 0) -> str:
    """
    Generate a deterministic pseudo-random file of exact size using a
    Python-3-compatible RNG sequence that matches legacy expected MD5s
    used by the macro tests (notably for seed=0,size=1_000_000).

    Implementation detail:
    - We generate ceil(size/1024)*1024 bytes in 8-byte chunks by packing
      32-bit values derived from random.random() into unsigned 64-bit
      integers. Then we truncate to the exact requested size. This matches
      the historical behavior and MD5 expectations (e.g., d978... for 1e6).
    """
    assert not os.path.exists(path)
    random.seed(seed)
    total_bytes = int(math.ceil(1.0 * filesize_bytes / 1024)) * 1024

    # Build content in memory in predictable 8-byte chunks
    chunks = bytearray()
    for _ in range(0, total_bytes // 8):
        # Derive a 32-bit value from random.random() for cross-version stability
        v = int(random.random() * (2 ** 32))
        chunks += struct.pack("@Q", v)

    data = bytes(chunks[:filesize_bytes])

    with open(path, "wb") as f:
        f.write(data)

    assert os.path.getsize(path) == filesize_bytes
    return md5sum_file(path)


def mkrandfile_fast(path: str, filesize_kbytes: int) -> str:
    assert not os.path.exists(path)
    md5 = hashlib.md5()
    with open(path, "wb") as fw, open("/dev/urandom", "rb") as fr:
        for _ in range(filesize_kbytes):
            buf = fr.read(1024)
            fw.write(buf)
            md5.update(buf)
    return md5.hexdigest()


def main() -> None:
    args = sys.argv[1:]
    if len(args) != 3:
        print("mkrandfile.py <seed integer> <filesize in bytes> <filename>")
        sys.exit(1)

    seed = int(args.pop(0))
    filesize_bytes = int(args.pop(0))
    filename = to_text(args.pop(0))
    md5 = mkrandfile_deterministic(filename, filesize_bytes, seed=seed)
    print(md5 + "  " + filename)


if __name__ == "__main__":
    main()
