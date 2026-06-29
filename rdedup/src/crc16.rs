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

//! Bit-exact port of cdedup/crc16.h.
//!
//! This is the CCITT CRC-16 implementation (reflected, polynomial 0x8408)
//! used to protect rows in the blocks database against silent corruption.
//! The arithmetic is performed with `u32` accumulators exactly as the
//! original C does (where `crc` and `data` are `unsigned int`), and the
//! result is truncated to `u16` on return.

const POLY: u32 = 0x8408;

/// Compute the CRC-16 of `data`, bit-for-bit identical to the C `crc16()`.
pub fn crc16(data: &[u8]) -> u16 {
    let mut crc: u32 = 0xffff;

    if data.is_empty() {
        return (!crc) as u16;
    }

    for &byte in data {
        let mut d: u32 = byte as u32;
        for _ in 0..8 {
            if ((crc & 0x0001) ^ (d & 0x0001)) != 0 {
                crc = (crc >> 1) ^ POLY;
            } else {
                crc >>= 1;
            }
            d >>= 1;
        }
    }

    crc = !crc;
    let data2 = crc;
    crc = (crc << 8) | ((data2 >> 8) & 0xff);
    crc as u16
}

#[cfg(test)]
mod tests {
    use super::crc16;

    #[test]
    fn empty_input() {
        // ~0xffff truncated to u16 == 0
        assert_eq!(crc16(b""), 0);
    }

    #[test]
    fn known_vectors() {
        // These values were produced by the reference C implementation.
        assert_eq!(crc16(b"123456789"), 0x6E90);
        assert_eq!(crc16(b"A"), 0xF5A3);
        assert_eq!(
            crc16(b"47bce5c74f589f4867dbd57e9ca9f808!0!47bce5c74f589f4867dbd57e9ca9f808!"),
            56355
        );
    }

    #[test]
    fn row_shape_is_deterministic() {
        let a = crc16(b"47bce5c74f589f4867dbd57e9ca9f808!0!47bce5c74f589f4867dbd57e9ca9f808!");
        let b = crc16(b"47bce5c74f589f4867dbd57e9ca9f808!0!47bce5c74f589f4867dbd57e9ca9f808!");
        assert_eq!(a, b);
    }
}
