# rdedup — boar's deduplication extension (Rust)

`rdedup` is boar's block-deduplication extension, a Rust/[PyO3](https://pyo3.rs)
implementation of the rolling-checksum / blocks-database primitives. It replaced
the original C/Cython `cdedup` extension (still in git history): it was developed
as a faithful, differentially-fuzzed port that produces bit-identical results and
reads/writes the same on-disk SQLite blocks-database format, and is faster on
every stage (the per-byte rolling scan ~1.7×).

It is exposed to the Python code under the name `cdedup` as well (registered in
`sys.modules`), so the historical `from cdedup import …` spelling keeps working.

## Public API

| Symbol | Description |
| --- | --- |
| `__version__` | `"1.0"` |
| `calc_rolling(bytes, window_size) -> int` | 64-bit rolling digest of a single block |
| `IntegerSet(bucket_count)` | `.add(int)`, `.add_all(iterable)`, `.contains(int) -> bool` |
| `RollingChecksum(window_size, IntegerSet)` | `.feed_string(bytes)`, iterate `(offset, rolling)` hits, `.value() -> int` |
| `BlocksDB(dbfile, block_size)` | SQLite block-location store with per-row CRC-16 integrity |
| `SoftCorruptionError` | re-exported from `boar_exceptions` |

## Layout

Each module ports the correspondingly-named source from the historical C
`cdedup` extension (see git history for the originals):

| File | Ports (historical cdedup source) |
| --- | --- |
| `src/crc16.rs` | `crc16.h` (CCITT CRC-16, reflected) |
| `src/rollsum.rs` | `rollsum.h` + `circularbuffer.h` |
| `src/intset.rs` | `intset.{c,h}` (backed by a `HashSet<u64>`) |
| `src/blocksdb.rs` | `blocksdb.{c,h}` (via `rusqlite`, bundled SQLite) |
| `src/lib.rs` | `cdedup.pyx` (the PyO3 module surface) |

## Build

```sh
make            # builds and installs ../rdedup.so
```

This requires a Rust toolchain (`cargo`); `PYO3_PYTHON` is pointed at the
interpreter to build against. The module is built with PyO3's `abi3` feature, so
a single compiled artifact works on any supported CPython. The `bundled` feature
of `rusqlite` compiles SQLite from source, so no system SQLite is needed.

## Test

```sh
make test       # Rust unit tests for the primitives (cargo test)
make check      # cargo test + the full boar deduplication suite on this module
```

Boar loads `rdedup` automatically when `rdedup.so` is present; set
`BOAR_DISABLE_DEDUP=1` to force the pure-Python fallback.
