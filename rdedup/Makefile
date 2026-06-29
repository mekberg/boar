# Build the rdedup Python extension module and install it at the repo root
# as ../rdedup.so, which boar's deduplication.py detects at runtime.

CARGO ?= cargo
PYTHON ?= python3

all: ../rdedup.so

../rdedup.so: src/lib.rs src/crc16.rs src/rollsum.rs src/intset.rs src/blocksdb.rs Cargo.toml
	PYO3_PYTHON=$$($(PYTHON) -c "import sys; print(sys.executable)") \
		$(CARGO) build --release --features extension-module
	cp -f target/release/librdedup.so ../rdedup.so

# Pure-Rust unit tests (links libpython; does not enable extension-module).
test:
	PYO3_PYTHON=$$($(PYTHON) -c "import sys; print(sys.executable)") $(CARGO) test

# Rust unit tests plus the full boar deduplication integration suite, run
# against this module (the only deduplication backend).
check: all test
	$(PYTHON) ../tests/test_deduplication.py

clean:
	$(CARGO) clean
	rm -f ../rdedup.so

.PHONY: all test check clean
