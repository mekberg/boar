#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright 2013 Mats Ekberg
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

"""Benchmark for the rolling-checksum identical-block finder in cdedup.

The deduplication code finds identical blocks across files in two
stages: BlockChecksum chops a reference stream into fixed-size blocks
and records the rolling checksum of each, and RollingChecksum then
slides a window over a target stream byte-by-byte, reporting every
offset whose rolling checksum matches a known block. This script
measures the throughput of both stages.

Three scenarios are timed, each reported in MiB/s of scanned data:

  1. harvest    - BlockChecksum splitting a stream into blocks
                  (one rolling checksum + one md5 per block).
  2. scan-miss  - RollingChecksum sliding over unrelated data; the
                  per-byte hot path with essentially no matches.
  3. scan-hit   - RollingChecksum sliding over a duplicate of the
                  reference; the hot path plus match handling.

Usage:
    python3 cdedup/benchmark-dedup.py [total_mib] [block_size]

Defaults: total_mib=64, block_size=65536 (the production block size).
Runs from any directory.
"""

import os
import sys
import time

# Allow running from anywhere by making the repo root importable.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deduplication import dedup_available, CreateIntegerSet

if not dedup_available:
    sys.exit("ERROR: deduplication module unavailable; build it with "
             "'make' in the cdedup directory first.")

from deduplication import BlockChecksum, RollingChecksum

MIB = 2 ** 20
CHUNK = MIB  # Feed data in 1 MiB chunks to keep memory bounded.


def make_data(size, seed):
    """Return `size` bytes of deterministic pseudo-random data."""
    import random
    rnd = random.Random(seed)
    return rnd.randbytes(size)


def harvest_blocks(data, block_size):
    """Split `data` into blocks, returning their rolling checksums.

    Also serves as the benchmark for the BlockChecksum stage when
    timed by the caller."""
    bc = BlockChecksum(block_size)
    rollings = []
    for pos in range(0, len(data), CHUNK):
        bc.feed_string(data[pos:pos + CHUNK])
        for _, rolling, _md5 in bc.harvest():
            rollings.append(rolling)
    return rollings


def scan(data, block_size, intset):
    """Slide a rolling checksum over `data`, returning the hit count."""
    rs = RollingChecksum(block_size, intset)
    hits = 0
    for pos in range(0, len(data), CHUNK):
        rs.feed_string(data[pos:pos + CHUNK])
        for _offset, _rolling in rs:
            hits += 1
    return hits


def report(name, nbytes, seconds, extra=""):
    rate = (nbytes / MIB) / seconds if seconds else float("inf")
    print("  %-10s %7.2f MiB in %6.3f s  =  %7.1f MiB/s   %s"
          % (name, nbytes / MIB, seconds, rate, extra))


def main():
    total_mib = int(sys.argv[1]) if len(sys.argv) > 1 else 64
    block_size = int(sys.argv[2]) if len(sys.argv) > 2 else 2 ** 16
    nbytes = total_mib * MIB

    print("cdedup rolling-checksum block-finder benchmark")
    print("  data size : %d MiB" % total_mib)
    print("  block size: %d bytes" % block_size)
    print("  blocks    : %d" % (nbytes // block_size))
    print()

    print("Generating test data...")
    reference = make_data(nbytes, seed=1)
    unrelated = make_data(nbytes, seed=2)
    print()

    # 1. Block harvesting: build the reference set of block checksums.
    t0 = time.time()
    rollings = harvest_blocks(reference, block_size)
    report("harvest", nbytes, time.time() - t0,
           "(%d blocks)" % len(rollings))

    intset = CreateIntegerSet(rollings)

    # 2. Scan unrelated data: the per-byte hot path with near-zero hits.
    t0 = time.time()
    misses_hits = scan(unrelated, block_size, intset)
    report("scan-miss", nbytes, time.time() - t0,
           "(%d hits)" % misses_hits)

    # 3. Scan a duplicate of the reference: hot path plus match handling.
    t0 = time.time()
    dup_hits = scan(reference, block_size, intset)
    report("scan-hit", nbytes, time.time() - t0,
           "(%d hits)" % dup_hits)


if __name__ == "__main__":
    main()
