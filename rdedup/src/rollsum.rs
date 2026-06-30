// Copyright 2013 Mats Ekberg
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//   http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

//! Bit-exact port of cdedup/rollsum.h + cdedup/circularbuffer.h.
//!
//! A rsync-style rolling checksum over a fixed-size window. The window
//! itself is a ring buffer holding the most recent `window_size` bytes;
//! the only byte ever read back is the one leaving the window during a
//! rotation, so the buffer is exactly window-sized.
//!
//! All accumulators are `u64` and every operation uses wrapping
//! (two's-complement) arithmetic, matching C's unsigned-integer overflow
//! semantics exactly. The 64-bit digest is `(s2 << 32) | s1`, identical
//! to `RollsumDigest64` in the original header.

use crate::intset::IntSet;

const ROLLSUM_CHAR_OFFSET: u64 = 31;

/// A match produced by [`RollingState::scan`]: the window starting at
/// `offset` has rolling digest `rolling`, and scanning should resume at
/// `next_pos` within the scanned slice.
pub struct ScanHit {
    pub offset: u64,
    pub rolling: u64,
    pub next_pos: usize,
}

/// Stateful rolling checksum with an embedded window ring buffer.
pub struct RollingState {
    count: u64,
    s1: u64,
    s2: u64,
    // Ring buffer of exactly `cap` bytes (the window).
    buf: Vec<u8>,
    cap: usize,
    pos: usize,    // index of the oldest byte (next to leave the window)
    length: usize, // bytes currently stored (<= cap)
}

impl RollingState {
    /// Create a rolling state over a window of `window_size` bytes.
    /// `window_size` must be positive (the C code asserts this).
    pub fn new(window_size: usize) -> Self {
        assert!(window_size > 0, "create_rolling(): window_size must be positive");
        RollingState {
            count: 0,
            s1: 0,
            s2: 0,
            buf: vec![0u8; window_size],
            cap: window_size,
            pos: 0,
            length: 0,
        }
    }

    /// Feed a single byte through the window. Mirrors `push_rolling()`.
    #[inline]
    pub fn push(&mut self, c: u8) {
        if self.length != self.cap {
            // Window not full yet: append (RollsumRollin).
            self.buf[self.length] = c;
            self.length += 1;

            self.s1 = self.s1.wrapping_add(c as u64 + ROLLSUM_CHAR_OFFSET);
            self.s2 = self.s2.wrapping_add(self.s1);
            self.count = self.count.wrapping_add(1);
        } else {
            // Window full: overwrite oldest byte and rotate (RollsumRotate).
            let out = self.buf[self.pos];
            self.buf[self.pos] = c;
            self.pos += 1;
            if self.pos == self.cap {
                self.pos = 0;
            }

            // s1 += in - out
            self.s1 = self
                .s1
                .wrapping_add((c as u64).wrapping_sub(out as u64));
            // s2 += s1 - count*(out + ROLLSUM_CHAR_OFFSET)
            self.s2 = self.s2.wrapping_add(
                self.s1.wrapping_sub(
                    self.count
                        .wrapping_mul((out as u64).wrapping_add(ROLLSUM_CHAR_OFFSET)),
                ),
            );
        }
    }

    /// Feed a whole buffer. Mirrors `push_buffer_rolling()`.
    #[allow(dead_code)] // mirrors the C API; used by tests
    pub fn push_buffer(&mut self, buf: &[u8]) {
        for &b in buf {
            self.push(b);
        }
    }

    /// The 64-bit rolling digest. Mirrors `value64_rolling()`.
    #[inline]
    pub fn value64(&self) -> u64 {
        (self.s2 << 32) | self.s1
    }

    /// The hot path: feed `buf[from..]` byte-by-byte, returning the first
    /// position (with at least `window` bytes fed) whose rolling digest is in
    /// `intset`, or `None` if the whole slice is consumed without a hit.
    ///
    /// `feeded` is the running total of bytes ever fed (across chunks) and is
    /// advanced as bytes are consumed. The accumulator and window state are
    /// kept in locals across the loop and written back once on exit, so the
    /// optimiser can keep them in registers — this is what closes the gap with
    /// the fully-inlined C inner loop.
    #[inline]
    pub fn scan(
        &mut self,
        buf: &[u8],
        from: usize,
        window: u64,
        feeded: &mut u64,
        skip_remaining: &mut u64,
        intset: &IntSet,
    ) -> Option<ScanHit> {
        let mut s1 = self.s1;
        let mut s2 = self.s2;
        let mut count = self.count;
        let mut pos = self.pos;
        let mut length = self.length;
        let cap = self.cap;
        let mut fed = *feeded;
        let mut skip = *skip_remaining;

        // Debug-only check that the ring-buffer invariants the unchecked
        // accesses below rely on actually hold on entry.
        debug_assert_eq!(self.buf.len(), cap);
        debug_assert!(pos < cap && length <= cap);

        let mut result = None;
        for (k, &byte) in buf[from..].iter().enumerate() {
            let c = byte as u64;
            if length != cap {
                // SAFETY: in this branch length < cap == self.buf.len().
                unsafe { *self.buf.get_unchecked_mut(length) = byte };
                length += 1;
                s1 = s1.wrapping_add(c + ROLLSUM_CHAR_OFFSET);
                s2 = s2.wrapping_add(s1);
                count = count.wrapping_add(1);
            } else {
                // SAFETY: pos is always < cap == self.buf.len().
                let out = unsafe { *self.buf.get_unchecked(pos) } as u64;
                unsafe { *self.buf.get_unchecked_mut(pos) = byte };
                pos += 1;
                if pos == cap {
                    pos = 0;
                }
                s1 = s1.wrapping_add(c.wrapping_sub(out));
                s2 = s2.wrapping_add(
                    s1.wrapping_sub(count.wrapping_mul(out.wrapping_add(ROLLSUM_CHAR_OFFSET))),
                );
            }
            fed += 1;
            if skip > 0 {
                // Inside a post-hit skip: the rolling state is still advanced
                // (above), but the position is not reported - it overlaps a
                // confirmed hit and the caller would discard it anyway.
                skip -= 1;
                continue;
            }
            if fed >= window {
                let rolling = (s2 << 32) | s1;
                if intset.contains(rolling) {
                    result = Some(ScanHit {
                        offset: fed - window,
                        rolling,
                        next_pos: from + k + 1,
                    });
                    break;
                }
            }
        }

        self.s1 = s1;
        self.s2 = s2;
        self.count = count;
        self.pos = pos;
        self.length = length;
        *feeded = fed;
        *skip_remaining = skip;
        result
    }
}

/// Compute the rolling-checksum digest of a single block directly, with no
/// allocation. A block no larger than the window never rotates the window,
/// so its digest is just the roll-in accumulation. Mirrors
/// `calc_rolling_digest()`.
pub fn calc_rolling_digest(buf: &[u8]) -> u64 {
    let mut s1: u64 = 0;
    let mut s2: u64 = 0;
    for &b in buf {
        s1 = s1.wrapping_add(b as u64 + ROLLSUM_CHAR_OFFSET);
        s2 = s2.wrapping_add(s1);
    }
    (s2 << 32) | s1
}

#[cfg(test)]
mod tests {
    use super::{calc_rolling_digest, RollingState};

    #[test]
    fn digest_known_vectors() {
        // Captured from the reference cdedup.calc_rolling().
        assert_eq!(calc_rolling_digest(b""), 0);
        assert_eq!(calc_rolling_digest(b"a"), 549755814016);
        assert_eq!(calc_rolling_digest(b"abc"), 3315714752899);
        assert_eq!(calc_rolling_digest(b"aaa"), 3298534883712);
        assert_eq!(calc_rolling_digest(b"XaaaX"), 8014408974958);
    }

    #[test]
    fn state_matches_direct_digest_when_no_rotation() {
        // A block not larger than the window must produce the same value
        // whether fed byte-by-byte or computed directly.
        let mut st = RollingState::new(3);
        st.push_buffer(b"abc");
        assert_eq!(st.value64(), calc_rolling_digest(b"abc"));
    }

    #[test]
    #[ignore] // timing probe: `cargo test --release -- --ignored --nocapture bench_scan`
    fn bench_scan() {
        use super::super::intset::IntSet;
        use std::time::Instant;
        let n: usize = 64 * 1024 * 1024;
        let window = 65536u64;
        // Deterministic pseudo-random bytes via a cheap LCG.
        let mut data = vec![0u8; n];
        let mut x: u64 = 0x1234_5678;
        for b in data.iter_mut() {
            x = x.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407);
            *b = (x >> 33) as u8;
        }
        // ~1024 block digests in a 100k-sized set, like CreateIntegerSet.
        let mut iset = IntSet::new(100_000);
        let mut i = 0;
        while i + window as usize <= n {
            iset.add(calc_rolling_digest(&data[i..i + window as usize]));
            i += window as usize;
        }
        let mut st = RollingState::new(window as usize);
        let mut fed = 0u64;
        let mut skip = 0u64;
        let mut hits = 0usize;
        let t0 = Instant::now();
        let mut pos = 0usize;
        loop {
            match st.scan(&data, pos, window, &mut fed, &mut skip, &iset) {
                Some(h) => {
                    hits += 1;
                    pos = h.next_pos;
                }
                None => break,
            }
        }
        let secs = t0.elapsed().as_secs_f64();
        eprintln!(
            "bench_scan: {} MiB in {:.3} s = {:.1} MiB/s ({} hits)",
            n / (1024 * 1024),
            secs,
            (n as f64 / (1024.0 * 1024.0)) / secs,
            hits
        );
    }

    #[test]
    fn rolling_window_finds_block_at_offset() {
        // Feeding "XXXaaaXXX" with window 3 must, at the moment the window
        // exactly covers "aaa", read the digest of "aaa".
        let target = calc_rolling_digest(b"aaa");
        let data = b"XXXaaaXXX";
        let window = 3usize;
        let mut st = RollingState::new(window);
        let mut hit_offset = None;
        for (i, &b) in data.iter().enumerate() {
            st.push(b);
            let fed = i + 1;
            if fed >= window && st.value64() == target {
                hit_offset = Some(fed - window);
                break;
            }
        }
        assert_eq!(hit_offset, Some(3));
    }
}
