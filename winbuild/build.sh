#!/bin/bash
# In-container pipeline: cross-compile rdedup.pyd, validate it under wine, freeze
# boar.exe with PyInstaller, then smoke-test the exe. Driven by winbuild/Dockerfile.
#
#   /src  : the boar repo, bind-mounted read-only
#   /out  : output dir on the host (gets rdedup.pyd and dist/boar.exe)
set -euo pipefail

SRC=/src
OUT=/out
WINPY=/opt/winpython/tools
# Windows Python under wine, headless. $PY runs the interpreter; env vars set on
# the command line propagate through wine into the Windows process.
PY=( xvfb-run -a wine64 "${WINPY}/python.exe" )

mkdir -p "$OUT"

echo "============================================================"
echo "[1/4] Cross-compiling rdedup.pyd  (x86_64-pc-windows-gnu, abi3)"
echo "============================================================"
export CARGO_TARGET_DIR=/tmp/target
export CARGO_TARGET_X86_64_PC_WINDOWS_GNU_LINKER=x86_64-w64-mingw32-gcc
export CC_x86_64_pc_windows_gnu=x86_64-w64-mingw32-gcc
export AR_x86_64_pc_windows_gnu=x86_64-w64-mingw32-ar
# PyO3 cross-compilation: abi3 only needs the version floor + the import lib dir.
export PYO3_CROSS=1
export PYO3_CROSS_PYTHON_VERSION=3.11
export PYO3_CROSS_LIB_DIR="${WINPY}/libs"

# Keep wine from launching propsys-using helpers (winemenubuilder) behind our back.
export WINEDLLOVERRIDES="winemenubuilder.exe=d"

cargo build --release --locked \
  --manifest-path "$SRC/rdedup/Cargo.toml" \
  --features extension-module \
  --target x86_64-pc-windows-gnu

cp "/tmp/target/x86_64-pc-windows-gnu/release/rdedup.dll" "$OUT/rdedup.pyd"
echo "-> $OUT/rdedup.pyd"
file "$OUT/rdedup.pyd" || true

# Build a writable working copy of the repo with rdedup.pyd dropped in, so the
# Windows interpreter (which only sees a Z:\ mapping of '/') can import it the
# same way the tests and the frozen exe will.
#
# The rdedup/ source dir is excluded: it has no __init__.py, so Python would
# otherwise treat it as an empty *namespace package* and `import rdedup` would
# resolve to the source dir instead of loading the .pyd. The cdedup.py shim
# (which re-exports rdedup under the historical name) is kept on purpose.
WORK=/tmp/boar
rm -rf "$WORK"; mkdir -p "$WORK"
( cd "$SRC" && tar -cf - \
    --exclude=.git --exclude=rdedup --exclude='*.so' --exclude='*.pyd' . ) \
  | ( cd "$WORK" && tar -xf - )
cp "$OUT/rdedup.pyd" "$WORK/rdedup.pyd"
cp "${WINPY}/python3.dll" "$WORK/python3.dll"   # bundled alongside the .pyd for PyInstaller

echo
echo "============================================================"
echo "[2/4] Validating rdedup under wine"
echo "============================================================"
( cd "$WORK" && "${PY[@]}" -c "import rdedup; print('rdedup __version__ =', rdedup.__version__)" )
echo "--- the cdedup compatibility shim resolves to rdedup ---"
( cd "$WORK" && "${PY[@]}" -c "import cdedup; print('cdedup ->', cdedup.__name__, cdedup.__version__)" )
echo "--- full deduplication suite ---"
( cd "$WORK" && "${PY[@]}" tests/test_deduplication.py )

echo
echo "============================================================"
echo "[3/4] Freezing boar.exe  (PyInstaller --onefile)"
echo "============================================================"
( cd "$WORK" && "${PY[@]}" -m PyInstaller winbuild/boar.spec \
    --distpath "$OUT/dist" --workpath /tmp/pyi --noconfirm )
echo "-> $OUT/dist/boar.exe"
file "$OUT/dist/boar.exe" || true

echo
echo "============================================================"
echo "[4/4] Smoke-testing boar.exe under wine"
echo "============================================================"
EXE="$OUT/dist/boar.exe"
RUN=( xvfb-run -a wine64 "$EXE" )

echo "--- confirm the bundled backend is really rdedup (not the python fallback) ---"
# Hard gate: boar_entry.py exits non-zero if dedup is unavailable. Capture the
# output and assert the native backend is actually active, so a broken freeze
# (e.g. the dedup module silently not bundled) fails the build here.
selftest_out=$(BOAR_WINBUILD_SELFTEST=1 "${RUN[@]}")
echo "$selftest_out"
echo "$selftest_out" | grep -q "dedup_available=True" \
  || { echo "ERROR: frozen exe has no working deduplication backend"; exit 1; }

SMOKE=/tmp/smoke
rm -rf "$SMOKE"; mkdir -p "$SMOKE/data"
# Two identical large files so deduplication actually has something to do.
# (dd, not `yes | head`: the latter trips SIGPIPE under set -o pipefail.)
dd if=/dev/urandom of="$SMOKE/data/a.bin" bs=1600000 count=1 status=none
cp "$SMOKE/data/a.bin" "$SMOKE/data/b.bin"

( cd "$SMOKE" \
  && xvfb-run -a wine64 "$EXE" mkrepo -d testrepo \
  && xvfb-run -a wine64 "$EXE" --repo testrepo mksession mysession \
  && xvfb-run -a wine64 "$EXE" --repo testrepo import data mysession \
  && xvfb-run -a wine64 "$EXE" --repo testrepo verify )

echo
echo "============================================================"
echo "DONE.  Deliverable: $OUT/dist/boar.exe"
echo "============================================================"
