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

//! Port of cdedup/intset.{c,h}.
//!
//! `contains()` runs once per scanned byte from the rolling-checksum hot
//! loop, and its bucket lookup address depends on the current rolling digest
//! — a sequential dependency, so the load latency cannot be hidden by
//! out-of-order execution. The dominant cost is therefore the cache level the
//! per-byte probe lands in.
//!
//! Like the C original we use a power-of-two bucket array indexed by the
//! value's low bits with a per-bucket OR-mask early-out. But we store the
//! masks in their own dense array (struct-of-arrays), so the per-byte probe
//! touches only an 8-bytes-per-bucket region (≈L2) instead of a fat
//! interleaved bucket struct (≈L3). The slot vectors are consulted only on
//! the rare mask pass.

pub struct IntSet {
    value_count: usize,
    bucket_count: usize, // always a power of two
    masks: Vec<u64>,     // hot: OR of every value in the bucket
    slots: Vec<Vec<u64>>, // cold: the values themselves
}

#[inline]
fn round_up_pow2(n: usize) -> usize {
    let mut c = 1usize;
    while c < n {
        c <<= 1;
    }
    c
}

impl IntSet {
    /// Create a set sized for roughly `bucket_count` entries. The C API
    /// requires a power of two; we round up so callers need not.
    pub fn new(bucket_count: usize) -> Self {
        let bucket_count = round_up_pow2(bucket_count.max(1));
        IntSet {
            value_count: 0,
            bucket_count,
            masks: vec![0u64; bucket_count],
            slots: (0..bucket_count).map(|_| Vec::new()).collect(),
        }
    }

    #[inline]
    fn index(&self, value: u64) -> usize {
        // bucket_count is a power of two, so & (bucket_count - 1) == % bucket_count.
        (value as usize) & (self.bucket_count - 1)
    }

    pub fn add(&mut self, value: u64) {
        let idx = self.index(value);
        self.masks[idx] |= value;
        self.slots[idx].push(value);
        self.value_count += 1;
        if self.value_count > self.bucket_count {
            self.grow();
        }
    }

    fn grow(&mut self) {
        let mut grown = IntSet::new(self.bucket_count * 2);
        for bucket in &self.slots {
            for &value in bucket {
                grown.add(value);
            }
        }
        *self = grown;
    }

    #[inline]
    pub fn contains(&self, value: u64) -> bool {
        let idx = self.index(value);
        // SAFETY: index() masks with bucket_count - 1, and masks.len() ==
        // bucket_count, so idx is always in bounds.
        let mask = unsafe { *self.masks.get_unchecked(idx) };
        if (mask & value) != value {
            return false;
        }
        // Rare path: the mask admitted this value; confirm against the slots.
        unsafe { self.slots.get_unchecked(idx) }
            .iter()
            .any(|&s| s == value)
    }

    #[allow(dead_code)] // part of the API surface; used by tests
    pub fn len(&self) -> usize {
        self.value_count
    }
}

#[cfg(test)]
mod tests {
    use super::IntSet;

    #[test]
    fn basic_membership() {
        let mut s = IntSet::new(1);
        assert!(!s.contains(42));
        s.add(42);
        assert!(s.contains(42));
        assert!(!s.contains(43));
    }

    #[test]
    fn handles_full_u64_range() {
        let mut s = IntSet::new(4);
        s.add(0);
        s.add(u64::MAX);
        assert!(s.contains(0));
        assert!(s.contains(u64::MAX));
        assert!(!s.contains(1));
    }

    #[test]
    fn duplicates_count_but_membership_is_stable() {
        let mut s = IntSet::new(1);
        s.add(7);
        s.add(7);
        assert!(s.contains(7));
    }

    #[test]
    fn growth_preserves_all_members() {
        // Force several growth steps and verify every value survives.
        let mut s = IntSet::new(1);
        let values: Vec<u64> = (0..10_000u64).map(|i| i.wrapping_mul(2654435761)).collect();
        for &v in &values {
            s.add(v);
        }
        for &v in &values {
            assert!(s.contains(v), "missing value {}", v);
        }
        assert!(!s.contains(0xdead_beef_dead_beef));
    }
}
