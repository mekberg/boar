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

//! Port of cdedup/blocksdb.{c,h}.
//!
//! The SQLite-backed store of block locations and rolling checksums. The
//! on-disk schema, the packed-binary md5 columns, and the per-row CRC-16
//! integrity check are all reproduced exactly so that databases written by
//! the original C `cdedup` and by `rdedup` are byte-for-byte interchangeable.

use std::time::Duration;

use rusqlite::{params, Connection};

use crate::crc16::crc16;

const MAGIC_BLOCK_SIZE_PROP: &str = "block_size";

/// Result-kind discriminator mirroring `BLOCKSDB_RESULT`'s error variants.
#[derive(Debug)]
pub enum ErrKind {
    /// The database (or a row in it) is corrupt -> SoftCorruptionError.
    Corrupt,
    /// Any other error -> a generic exception.
    Other,
}

#[derive(Debug)]
pub struct BlocksDbError {
    pub kind: ErrKind,
    pub message: String,
}

impl BlocksDbError {
    fn corrupt(message: impl Into<String>) -> Self {
        BlocksDbError { kind: ErrKind::Corrupt, message: message.into() }
    }
    fn other(message: impl Into<String>) -> Self {
        BlocksDbError { kind: ErrKind::Other, message: message.into() }
    }
}

type Result<T> = std::result::Result<T, BlocksDbError>;

// ---------------------------------------------------------------------------
// md5 hex <-> binary helpers (port of hexchar2bin / is_md5sum / hex2bin /
// bin2hex / pack_md5 / unpack_md5)
// ---------------------------------------------------------------------------

fn hexchar2bin(c: u8) -> i32 {
    match c {
        b'0'..=b'9' => (c - b'0') as i32,
        b'a'..=b'f' => (c - b'a' + 10) as i32,
        b'A'..=b'F' => (c - b'A' + 10) as i32,
        _ => -1,
    }
}

/// True iff `buf` is exactly 32 hexadecimal characters.
pub fn is_md5sum(buf: &[u8]) -> bool {
    buf.len() == 32 && buf.iter().all(|&c| hexchar2bin(c) != -1)
}

/// Pack a 32-char md5 hex string into 16 bytes. Caller must have validated
/// `hex` with `is_md5sum`.
fn pack_md5(hex: &[u8]) -> [u8; 16] {
    let mut out = [0u8; 16];
    for i in 0..16 {
        out[i] = ((hexchar2bin(hex[i * 2]) << 4) | hexchar2bin(hex[i * 2 + 1])) as u8;
    }
    out
}

/// Unpack 16 binary bytes into a 32-char lowercase md5 hex byte string.
fn unpack_md5(bin: &[u8]) -> Vec<u8> {
    const HEX: &[u8; 16] = b"0123456789abcdef";
    let mut out = Vec::with_capacity(32);
    for &b in bin {
        out.push(HEX[(b >> 4) as usize]);
        out.push(HEX[(b & 0x0f) as usize]);
    }
    out
}

/// Compute the per-row CRC-16 over "blob!offset!md5!" exactly as
/// `crc16_row()` does (offset rendered as decimal, hashes as hex).
fn crc16_row(blob_hex: &[u8], offset: u64, md5_hex: &[u8]) -> u16 {
    let mut data = Vec::with_capacity(blob_hex.len() + md5_hex.len() + 24);
    data.extend_from_slice(blob_hex);
    data.push(b'!');
    data.extend_from_slice(offset.to_string().as_bytes());
    data.push(b'!');
    data.extend_from_slice(md5_hex);
    data.push(b'!');
    crc16(&data)
}

// ---------------------------------------------------------------------------
// BlocksDb
// ---------------------------------------------------------------------------

pub struct BlocksDb {
    conn: Connection,
}

impl BlocksDb {
    /// Open (creating/initialising as needed) the blocks database, mirroring
    /// `init_blocksdb` + `initialize_database`.
    pub fn open(dbfile: &str, block_size: i64) -> Result<BlocksDb> {
        let conn = Connection::open(dbfile)
            .map_err(|e| BlocksDbError::corrupt(format!("Error while opening database {}: {}", dbfile, e)))?;
        conn.busy_timeout(Duration::from_millis(10 * 60 * 1000))
            .map_err(|e| BlocksDbError::other(format!("busy_timeout failed: {}", e)))?;

        let db = BlocksDb { conn };
        db.initialize_database(block_size)?;
        Ok(db)
    }

    fn initialize_database(&self, block_size: i64) -> Result<()> {
        // Run the schema bootstrap in one exclusive transaction, exactly as
        // the C code does. On a non-database file the first statement fails
        // and we surface that as a corruption error.
        let script = format!(
            "PRAGMA main.locking_mode=NORMAL;\n\
             BEGIN EXCLUSIVE;\n\
             CREATE TABLE IF NOT EXISTS blocks (blob BLOB(16) NOT NULL, offset LONG NOT NULL, md5_short BLOB(4) NOT NULL, md5 BLOB(16) NOT NULL, row_crc INT NOT NULL);\n\
             CREATE TABLE IF NOT EXISTS rolling (value LONG NOT NULL);\n\
             CREATE TABLE IF NOT EXISTS props (name TEXT PRIMARY KEY, value TEXT);\n\
             INSERT OR IGNORE INTO props VALUES ('modification_counter', 0);\n\
             CREATE UNIQUE INDEX IF NOT EXISTS index_offset ON blocks (blob, offset);\n\
             CREATE INDEX IF NOT EXISTS index_block_md5 ON blocks (md5_short);\n\
             INSERT OR IGNORE INTO props VALUES ('block_size', {});\n\
             COMMIT;",
            block_size
        );
        self.conn
            .execute_batch(&script)
            .map_err(|e| BlocksDbError::corrupt(format!("Error while initializing database: {}", e)))?;

        let fetched = self.get_block_size()?;
        if fetched != block_size {
            return Err(BlocksDbError::other(format!(
                "Block size mismatch (stored {}, requested {})",
                fetched, block_size
            )));
        }
        Ok(())
    }

    pub fn get_block_size(&self) -> Result<i64> {
        // props.value has TEXT affinity, so the integer is stored as text.
        // CAST mirrors C's coercive sqlite3_column_int().
        self.conn
            .query_row(
                "SELECT CAST(value AS INTEGER) FROM props WHERE name = ?",
                params![MAGIC_BLOCK_SIZE_PROP],
                |row| row.get::<_, i64>(0),
            )
            .map_err(|e| BlocksDbError::other(format!("get_block_size() failed: {}", e)))
    }

    pub fn get_modcount(&self) -> Result<i64> {
        self.conn
            .query_row(
                "SELECT CAST(value AS INTEGER) FROM props WHERE name = 'modification_counter'",
                [],
                |row| row.get::<_, i64>(0),
            )
            .map_err(|e| BlocksDbError::other(format!("get_modcount() failed: {}", e)))
    }

    pub fn increment_modcount(&self) -> Result<()> {
        self.conn
            .execute(
                "UPDATE props SET value = value + 1 where name = 'modification_counter'",
                [],
            )
            .map(|_| ())
            .map_err(|e| BlocksDbError::other(format!("increment_modcount() failed: {}", e)))
    }

    pub fn begin(&self) -> Result<()> {
        self.exec_simple("BEGIN")
    }

    pub fn commit(&self) -> Result<()> {
        self.exec_simple("COMMIT")
    }

    fn exec_simple(&self, sql: &str) -> Result<()> {
        self.conn
            .execute_batch(sql)
            .map_err(|e| BlocksDbError::other(format!("{} failed: {}", sql, e)))
    }

    /// Mirror of `add_block`. `blob_hex` and `md5_hex` are 32-char hex.
    pub fn add_block(&self, blob_hex: &[u8], offset: u64, md5_hex: &[u8]) -> Result<()> {
        if !is_md5sum(blob_hex) {
            return Err(BlocksDbError::other(format!(
                "add_block(): Not a valid blob name: {}",
                String::from_utf8_lossy(blob_hex)
            )));
        }
        if !is_md5sum(md5_hex) {
            return Err(BlocksDbError::other(format!(
                "add_block(): Not a valid md5 sum: {}",
                String::from_utf8_lossy(md5_hex)
            )));
        }

        let row_crc = crc16_row(blob_hex, offset, md5_hex) as i64;
        let packed_md5 = pack_md5(md5_hex);
        let packed_blob = pack_md5(blob_hex);
        let md5_short = &packed_md5[0..4];

        self.conn
            .execute(
                "INSERT OR IGNORE INTO blocks (blob, offset, md5_short, md5, row_crc) VALUES (?, ?, ?, ?, ?)",
                params![
                    packed_blob.as_slice(),
                    offset as i64,
                    md5_short,
                    packed_md5.as_slice(),
                    row_crc
                ],
            )
            .map(|_| ())
            .map_err(|e| BlocksDbError::other(format!("Error while inserting new block: {}", e)))
    }

    /// Mirror of `get_blocks_*`. Returns (blob_hex_bytes, offset) pairs and
    /// verifies the per-row CRC, surfacing corruption as `ErrKind::Corrupt`.
    pub fn get_block_locations(&self, md5_hex: &[u8], limit: i64) -> Result<Vec<(Vec<u8>, u64)>> {
        if !is_md5sum(md5_hex) {
            return Err(BlocksDbError::other(format!(
                "get_blocks_init(): Not a valid md5 sum: {}",
                String::from_utf8_lossy(md5_hex)
            )));
        }
        let packed_md5 = pack_md5(md5_hex);
        let md5_short = &packed_md5[0..4];

        let mut stmt = self
            .conn
            .prepare(
                "SELECT blocks.blob, blocks.offset, blocks.row_crc, blocks.md5 FROM blocks \
                 WHERE md5_short = ? AND md5 = ? LIMIT ?",
            )
            .map_err(|e| BlocksDbError::other(format!("get_blocks_init() prepare failed: {}", e)))?;

        let mut rows = stmt
            .query(params![md5_short, packed_md5.as_slice(), limit])
            .map_err(|e| BlocksDbError::other(format!("get_blocks query failed: {}", e)))?;

        let mut result = Vec::new();
        loop {
            let row = match rows.next() {
                Ok(Some(row)) => row,
                Ok(None) => break,
                Err(e) => {
                    return Err(BlocksDbError::corrupt(format!(
                        "Unexpected result while reading blocks: {}",
                        e
                    )))
                }
            };

            let blob_col: Vec<u8> = row
                .get(0)
                .map_err(|e| BlocksDbError::other(format!("blob column read failed: {}", e)))?;
            if blob_col.len() != 16 {
                return Err(BlocksDbError::corrupt(
                    "Unexpected blob column length in get_blocks_next()",
                ));
            }
            let offset = row
                .get::<_, i64>(1)
                .map_err(|e| BlocksDbError::other(format!("offset column read failed: {}", e)))?
                as u64;
            let row_crc = row
                .get::<_, i64>(2)
                .map_err(|e| BlocksDbError::other(format!("row_crc column read failed: {}", e)))?;
            let md5_col: Vec<u8> = row
                .get(3)
                .map_err(|e| BlocksDbError::other(format!("md5 column read failed: {}", e)))?;
            if md5_col.len() != 16 {
                return Err(BlocksDbError::corrupt(
                    "Unexpected md5 column length in get_blocks_next()",
                ));
            }

            let blob_hex = unpack_md5(&blob_col);
            let md5_hex_row = unpack_md5(&md5_col);
            let expected_crc = crc16_row(&blob_hex, offset, &md5_hex_row) as i64;
            if row_crc != expected_crc {
                return Err(BlocksDbError::corrupt(format!(
                    "An entry in the blocks database is corrupt (block id {})",
                    String::from_utf8_lossy(&md5_hex_row)
                )));
            }

            result.push((blob_hex, offset));
        }
        Ok(result)
    }

    pub fn add_rolling(&self, rolling: u64) -> Result<()> {
        self.conn
            .execute(
                "INSERT INTO rolling (value) VALUES (?)",
                params![rolling as i64],
            )
            .map(|_| ())
            .map_err(|e| BlocksDbError::other(format!("add_rolling() failed: {}", e)))
    }

    pub fn get_all_rolling(&self) -> Result<Vec<u64>> {
        let mut stmt = self
            .conn
            .prepare("SELECT value FROM rolling")
            .map_err(|e| BlocksDbError::other(format!("get_rolling prepare failed: {}", e)))?;
        let rows = stmt
            .query_map([], |row| Ok(row.get::<_, i64>(0)? as u64))
            .map_err(|e| BlocksDbError::other(format!("get_rolling query failed: {}", e)))?;
        let mut out = Vec::new();
        for r in rows {
            out.push(r.map_err(|e| {
                BlocksDbError::other(format!("Error while fetching rolling checksums: {}", e))
            })?);
        }
        Ok(out)
    }

    /// Mirror of the `delete_blocks_*` sequence.
    pub fn delete_blocks(&self, blobs: &[Vec<u8>]) -> Result<()> {
        self.exec_simple("CREATE TEMPORARY TABLE blocks_to_delete (blob CHAR(16) PRIMARY KEY)")?;
        for blob in blobs {
            if !is_md5sum(blob) {
                return Err(BlocksDbError::other(format!(
                    "delete_blocks_add(): Not a valid blob name: {}",
                    String::from_utf8_lossy(blob)
                )));
            }
            let packed_blob = pack_md5(blob);
            self.conn
                .execute(
                    "INSERT OR IGNORE INTO blocks_to_delete (blob) VALUES (?)",
                    params![packed_blob.as_slice()],
                )
                .map_err(|e| {
                    BlocksDbError::other(format!("Error while adding blob to delete list: {}", e))
                })?;
        }
        self.exec_simple("DELETE FROM blocks WHERE blocks.blob IN blocks_to_delete")?;
        self.exec_simple("DROP TABLE blocks_to_delete")?;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn md5_validation() {
        assert!(is_md5sum(b"47bce5c74f589f4867dbd57e9ca9f808"));
        assert!(is_md5sum(b"D41D8CD98F00B204E9800998ECF8427E"));
        assert!(!is_md5sum(b"too short"));
        assert!(!is_md5sum(b"47bce5c74f589f4867dbd57e9ca9f80g")); // non-hex
        assert!(!is_md5sum(b"47bce5c74f589f4867dbd57e9ca9f8080")); // 33 chars
    }

    #[test]
    fn pack_unpack_roundtrip() {
        let hex = b"47bce5c74f589f4867dbd57e9ca9f808";
        let packed = pack_md5(hex);
        let back = unpack_md5(&packed);
        assert_eq!(&back, hex);
    }

    #[test]
    fn in_memory_block_roundtrip() {
        let db = BlocksDb::open(":memory:", 3).unwrap();
        db.begin().unwrap();
        db.add_block(
            b"47bce5c74f589f4867dbd57e9ca9f808",
            0,
            b"47bce5c74f589f4867dbd57e9ca9f808",
        )
        .unwrap();
        db.commit().unwrap();
        let locs = db
            .get_block_locations(b"47bce5c74f589f4867dbd57e9ca9f808", -1)
            .unwrap();
        assert_eq!(locs.len(), 1);
        assert_eq!(locs[0].0, b"47bce5c74f589f4867dbd57e9ca9f808".to_vec());
        assert_eq!(locs[0].1, 0);
    }

    #[test]
    fn rolling_roundtrip_full_range() {
        let db = BlocksDb::open(":memory:", 65536).unwrap();
        db.begin().unwrap();
        db.add_rolling(0).unwrap();
        db.add_rolling(u64::MAX).unwrap();
        db.commit().unwrap();
        let mut all = db.get_all_rolling().unwrap();
        all.sort();
        assert_eq!(all, vec![0, u64::MAX]);
    }

    #[test]
    fn high_offset_roundtrip() {
        let db = BlocksDb::open(":memory:", 65536).unwrap();
        db.begin().unwrap();
        let off = u64::MAX;
        db.add_block(b"d41d8cd98f00b204e9800998ecf8427e", off, b"00000000000000000000000000000001")
            .unwrap();
        db.commit().unwrap();
        let locs = db
            .get_block_locations(b"00000000000000000000000000000001", -1)
            .unwrap();
        assert_eq!(locs[0].1, off);
    }
}
