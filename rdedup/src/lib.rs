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

//! rdedup - a Rust/PyO3 port of boar's `cdedup` deduplication extension.
//!
//! This module is a drop-in replacement for `cdedup`: it exposes the same
//! Python API (`IntegerSet`, `RollingChecksum`, `calc_rolling`, `BlocksDB`,
//! `__version__`, and a re-exported `SoftCorruptionError`) with identical
//! observable behaviour and a byte-compatible on-disk blocks database.

mod blocksdb;
mod crc16;
mod intset;
mod rollsum;

use std::collections::{HashSet, VecDeque};

use pyo3::exceptions::{PyAssertionError, PyException};
use pyo3::prelude::*;
use pyo3::types::{PyByteArray, PyBytes};

use blocksdb::{BlocksDb, BlocksDbError, ErrKind};
use intset::IntSet;
use rollsum::{calc_rolling_digest, RollingState};

/// Major.minor version. Major bumps signal API changes; kept identical to
/// `cdedup.__version__` so `deduplication.py`'s compatibility assertion holds.
const VERSION: &str = "1.0";

// ---------------------------------------------------------------------------
// Error helpers
// ---------------------------------------------------------------------------

/// Build a `boar_exceptions.SoftCorruptionError` instance as a `PyErr`,
/// falling back to a plain exception if the module cannot be imported.
fn soft_corruption_error(py: Python<'_>, msg: &str) -> PyErr {
    match py
        .import_bound("boar_exceptions")
        .and_then(|m| m.getattr("SoftCorruptionError"))
        .and_then(|cls| cls.call1((msg,)))
    {
        Ok(inst) => PyErr::from_value_bound(inst),
        Err(_) => PyException::new_err(msg.to_string()),
    }
}

/// Map a low-level blocks-db error to the same Python exception `cdedup.pyx`
/// would have raised for this call site (corrupt -> SoftCorruptionError,
/// everything else -> a generic Exception).
fn map_db_error(py: Python<'_>, err: BlocksDbError) -> PyErr {
    match err.kind {
        ErrKind::Corrupt => soft_corruption_error(py, &err.message),
        ErrKind::Other => PyException::new_err(err.message),
    }
}

// ---------------------------------------------------------------------------
// IntegerSet
// ---------------------------------------------------------------------------

#[pyclass]
pub struct IntegerSet {
    inner: IntSet,
}

impl IntegerSet {
    /// Crate-internal access to the backing set for `RollingChecksum`'s hot
    /// scan loop.
    #[inline]
    fn inner_set(&self) -> &IntSet {
        &self.inner
    }
}

#[pymethods]
impl IntegerSet {
    #[new]
    fn new(bucket_count: usize) -> Self {
        // The C constructor rounds the bucket count up to a power of two;
        // for us it is only a capacity hint, so we pass it through.
        IntegerSet { inner: IntSet::new(bucket_count) }
    }

    fn add(&mut self, int_to_add: u64) {
        self.inner.add(int_to_add);
    }

    fn add_all(&mut self, ints_to_add: Vec<u64>) {
        for n in ints_to_add {
            self.inner.add(n);
        }
    }

    fn contains(&self, int_to_find: u64) -> bool {
        self.inner.contains(int_to_find)
    }
}

// ---------------------------------------------------------------------------
// RollingChecksum
// ---------------------------------------------------------------------------

#[pyclass]
pub struct RollingChecksum {
    state: RollingState,
    feeded_bytecount: u64,
    window_size: u64,
    feed_pos: usize,
    feed_s: Vec<u8>,
    feed_queue: VecDeque<Vec<u8>>,
    intset: Py<IntegerSet>,
}

#[pymethods]
impl RollingChecksum {
    #[new]
    fn new(window_size: i32, m_intset: Py<IntegerSet>) -> PyResult<Self> {
        if window_size <= 0 {
            return Err(PyAssertionError::new_err(
                "create_rolling(): window_size must be positive",
            ));
        }
        Ok(RollingChecksum {
            state: RollingState::new(window_size as usize),
            feeded_bytecount: 0,
            window_size: window_size as u64,
            feed_pos: 0,
            feed_s: Vec::new(),
            feed_queue: VecDeque::new(),
            intset: m_intset,
        })
    }

    /// Queue a chunk of data to be scanned. Accepts bytes; a str is encoded
    /// as UTF-8, matching the original's lenient behaviour.
    fn feed_string(&mut self, s: &Bound<'_, PyAny>) -> PyResult<()> {
        // Use the buffer protocol (zero-copy borrow + one memcpy). Extracting
        // Vec<u8> directly would fall back to PyO3's generic element-wise path,
        // converting each byte to a Python int — catastrophically slow on the
        // megabyte chunks the scanner is fed.
        let bytes: Vec<u8> = if let Ok(b) = s.downcast::<PyBytes>() {
            b.as_bytes().to_vec()
        } else if let Ok(ba) = s.downcast::<PyByteArray>() {
            ba.to_vec()
        } else {
            let st: String = s.extract()?;
            st.into_bytes()
        };
        self.feed_queue.push_back(bytes);
        Ok(())
    }

    fn __iter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> {
        slf
    }

    /// Advance the scan, returning the next `(offset, rolling)` hit whose
    /// window digest is present in the associated IntegerSet, or `None`
    /// (StopIteration) when the queued data is exhausted.
    fn __next__(mut slf: PyRefMut<'_, Self>) -> PyResult<Option<(u64, u64)>> {
        let py = slf.py();
        // Detach an owned handle to the int-set so we can hold its borrow
        // across the scan loop without aliasing `slf`.
        let intset_handle = slf.intset.clone_ref(py);
        let intset_guard = intset_handle.bind(py).borrow();
        let intset = intset_guard.inner_set();
        let window = slf.window_size;

        // Disjoint borrows of `slf`'s fields let the per-byte loop live
        // entirely inside `RollingState::scan` with state in registers.
        let this = &mut *slf;
        loop {
            if this.feed_pos == this.feed_s.len() {
                match this.feed_queue.pop_front() {
                    Some(s) => {
                        this.feed_s = s;
                        this.feed_pos = 0;
                    }
                    None => return Ok(None), // StopIteration
                }
            }
            match this.state.scan(
                &this.feed_s,
                this.feed_pos,
                window,
                &mut this.feeded_bytecount,
                intset,
            ) {
                Some(hit) => {
                    this.feed_pos = hit.next_pos;
                    return Ok(Some((hit.offset, hit.rolling)));
                }
                None => {
                    this.feed_pos = this.feed_s.len();
                }
            }
        }
    }

    /// Drive the scan to exhaustion (ignoring hits) and return the current
    /// 64-bit rolling digest. Mirrors `RollingChecksum.value()`.
    fn value(mut slf: PyRefMut<'_, Self>) -> u64 {
        loop {
            if slf.feed_pos == slf.feed_s.len() {
                match slf.feed_queue.pop_front() {
                    Some(s) => {
                        slf.feed_s = s;
                        slf.feed_pos = 0;
                    }
                    None => break,
                }
            }
            while slf.feed_pos < slf.feed_s.len() {
                let c = slf.feed_s[slf.feed_pos];
                slf.state.push(c);
                slf.feeded_bytecount += 1;
                slf.feed_pos += 1;
            }
        }
        slf.state.value64()
    }
}

// ---------------------------------------------------------------------------
// calc_rolling
// ---------------------------------------------------------------------------

/// Convenience function: the rolling digest of a single block no larger than
/// `window_size`. Mirrors `cdedup.calc_rolling`.
#[pyfunction]
fn calc_rolling(s: &[u8], window_size: usize) -> PyResult<u64> {
    if s.len() > window_size {
        return Err(PyAssertionError::new_err("calc_rolling: block larger than window"));
    }
    Ok(calc_rolling_digest(s))
}

// ---------------------------------------------------------------------------
// BlocksDB (combines the C handle and the pyx-level wrapper logic)
// ---------------------------------------------------------------------------

#[pyclass]
pub struct BlocksDB {
    db: BlocksDb,
    in_transaction: bool,
    all_rolling: HashSet<u64>,
    is_modified: bool,
    last_seen_modcount: i64,
    rolling_loaded: bool,
}

impl BlocksDB {
    fn load_rolling_lazy(&mut self) -> Result<(), BlocksDbError> {
        if self.rolling_loaded {
            return Ok(());
        }
        self.rolling_loaded = true;
        self.reload_rolling()
    }

    fn reload_rolling(&mut self) -> Result<(), BlocksDbError> {
        let rolling = self.db.get_all_rolling()?;
        self.all_rolling = rolling.into_iter().collect();
        self.last_seen_modcount = self.db.get_modcount()?;
        Ok(())
    }
}

#[pymethods]
impl BlocksDB {
    #[new]
    fn new(py: Python<'_>, dbfile: &Bound<'_, PyAny>, block_size: i64) -> PyResult<Self> {
        // dbfile may be str or bytes (utf-8), as in cdedup.pyx.
        let path: String = if let Ok(s) = dbfile.extract::<String>() {
            s
        } else {
            let raw: Vec<u8> = dbfile.extract()?;
            String::from_utf8(raw)
                .map_err(|e| PyException::new_err(format!("dbfile is not valid utf-8: {}", e)))?
        };
        // The pyx __init__ raises SoftCorruptionError for *any* init failure.
        let db = BlocksDb::open(&path, block_size)
            .map_err(|e| soft_corruption_error(py, &e.message))?;
        Ok(BlocksDB {
            db,
            in_transaction: false,
            all_rolling: HashSet::new(),
            is_modified: false,
            last_seen_modcount: -1,
            rolling_loaded: false,
        })
    }

    fn get_all_rolling(&mut self, py: Python<'_>) -> PyResult<Vec<u64>> {
        self.load_rolling_lazy().map_err(|e| map_db_error(py, e))?;
        self.db.get_all_rolling().map_err(|e| map_db_error(py, e))
    }

    fn has_block(&self, py: Python<'_>, md5: &[u8]) -> PyResult<bool> {
        let locs = self
            .db
            .get_block_locations(md5, 1)
            .map_err(|e| map_db_error(py, e))?;
        Ok(!locs.is_empty())
    }

    #[pyo3(signature = (md5, limit = -1))]
    fn get_block_locations(
        &self,
        py: Python<'_>,
        md5: &[u8],
        limit: i64,
    ) -> PyResult<Vec<(Py<PyBytes>, u64)>> {
        let locs = self
            .db
            .get_block_locations(md5, limit)
            .map_err(|e| map_db_error(py, e))?;
        Ok(locs
            .into_iter()
            .map(|(blob, offset)| (PyBytes::new_bound(py, &blob).unbind(), offset))
            .collect())
    }

    fn add_rolling(&mut self, py: Python<'_>, rolling: u64) -> PyResult<()> {
        self.load_rolling_lazy().map_err(|e| map_db_error(py, e))?;
        if !self.in_transaction {
            return Err(PyAssertionError::new_err(
                "Tried to add a rolling cs outside of a transaction",
            ));
        }
        if !self.all_rolling.contains(&rolling) {
            self.all_rolling.insert(rolling);
            self.is_modified = true;
            self.db.add_rolling(rolling).map_err(|e| map_db_error(py, e))?;
        }
        Ok(())
    }

    fn delete_blocks(&mut self, py: Python<'_>, blobs: Vec<Vec<u8>>) -> PyResult<()> {
        if !self.in_transaction {
            return Err(PyAssertionError::new_err(
                "Tried to delete blocks outside of a transaction",
            ));
        }
        self.db.delete_blocks(&blobs).map_err(|e| map_db_error(py, e))
    }

    fn add_block(&mut self, py: Python<'_>, blob: &[u8], offset: u64, md5: &[u8]) -> PyResult<()> {
        if !self.in_transaction {
            return Err(PyAssertionError::new_err(
                "Tried to add a block outside of a transaction",
            ));
        }
        self.db
            .add_block(blob, offset, md5)
            .map_err(|e| map_db_error(py, e))?;
        self.is_modified = true;
        Ok(())
    }

    fn begin(&mut self, py: Python<'_>) -> PyResult<()> {
        self.load_rolling_lazy().map_err(|e| map_db_error(py, e))?;
        if self.in_transaction {
            return Err(PyAssertionError::new_err(
                "Tried to start a transaction while one was already in progress",
            ));
        }
        self.db.begin().map_err(|e| map_db_error(py, e))?;
        let current = self.db.get_modcount().map_err(|e| map_db_error(py, e))?;
        if self.last_seen_modcount != current {
            self.reload_rolling().map_err(|e| map_db_error(py, e))?;
        }
        self.in_transaction = true;
        Ok(())
    }

    fn commit(&mut self, py: Python<'_>) -> PyResult<()> {
        if !self.in_transaction {
            return Err(PyAssertionError::new_err(
                "Tried to do a commit while no transaction was in progress",
            ));
        }
        self.in_transaction = false;
        if self.is_modified {
            self.db
                .increment_modcount()
                .map_err(|e| map_db_error(py, e))?;
            self.is_modified = false;
        }
        self.last_seen_modcount = self.db.get_modcount().map_err(|e| map_db_error(py, e))?;
        self.db.commit().map_err(|e| map_db_error(py, e))
    }

    fn get_block_size(&self, py: Python<'_>) -> PyResult<i64> {
        self.db.get_block_size().map_err(|e| map_db_error(py, e))
    }
}

// ---------------------------------------------------------------------------
// Module definition
// ---------------------------------------------------------------------------

#[pymodule]
fn rdedup(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("__version__", VERSION)?;
    m.add_class::<IntegerSet>()?;
    m.add_class::<RollingChecksum>()?;
    m.add_class::<BlocksDB>()?;
    m.add_function(wrap_pyfunction!(calc_rolling, m)?)?;

    // Re-export SoftCorruptionError, mirroring cdedup's namespace.
    let py = m.py();
    if let Ok(exc) = py
        .import_bound("boar_exceptions")
        .and_then(|m2| m2.getattr("SoftCorruptionError"))
    {
        m.add("SoftCorruptionError", exc)?;
    }
    Ok(())
}
