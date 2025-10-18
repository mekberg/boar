PYTHON ?= python3

DEST_EXT := $(strip $(shell $(PYTHON) - <<'PY'
import os
print('.pyd' if os.name == 'nt' else '.so')
PY
))

DEST_FILE := ../cdedup$(DEST_EXT)

all: $(DEST_FILE)

$(DEST_FILE): blocksdb.c blocksdb.h rollsum.c rollsum.h intset.c intset.h circularbuffer.h circularbuffer.c setup-cython.py crc16.h Makefile cdedup.pyx
	$(PYTHON) setup-cython.py build_ext --inplace
	$(PYTHON) - <<'PY'
import os
import shutil
from pathlib import Path

base = Path('.').resolve()
root = base.parent
candidates = sorted(list(base.glob('cdedup*.so')) + list(base.glob('cdedup*.pyd')), key=lambda p: p.stat().st_mtime, reverse=True)
if not candidates:
    raise SystemExit('No built cdedup extension found')
dest = root / ('cdedup.pyd' if os.name == 'nt' else 'cdedup.so')
shutil.copy2(candidates[0], dest)
print(f'Copied {candidates[0].name} -> {dest.name}')
PY

.PHONY: clean

clean:
	rm -f ../cdedup.so ../cdedup.pyd
	rm -f cdedup*.so cdedup*.pyd cdedup.c sqlite3.c sqlite3.h

