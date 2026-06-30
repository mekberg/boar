# PyInstaller entry shim for the frozen boar.exe.
#
# The real entry point is the repo-root script named "boar" (no .py extension),
# which PyInstaller cannot analyse well and whose command dispatch lives behind
# an `if __name__ == "__main__"` guard. We bundle that script as data and run it
# verbatim via runpy, so the frozen exe behaves exactly like `python boar ...`.
#
# All of boar's real imports are declared as hiddenimports in boar.spec, since
# running the script through runpy hides them from static analysis.
import os
import sys
import runpy

# The deduplication backend is the bundled Rust rdedup.pyd (set
# BOAR_DISABLE_DEDUP=1 to force the pure-Python fallback).

if getattr(sys, "frozen", False):
    base = sys._MEIPASS
else:
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Build-time self test: confirm the native dedup backend is bundled and active.
if os.environ.get("BOAR_WINBUILD_SELFTEST") == "1":
    import deduplication
    backend = getattr(deduplication, "cdedup", None)
    print("BOAR_WINBUILD_SELFTEST: dedup_available=%r backend=%r version=%r" % (
        deduplication.dedup_available,
        getattr(backend, "__name__", None),
        deduplication.cdedup_version,
    ))
    sys.exit(0 if deduplication.dedup_available else 1)

runpy.run_path(os.path.join(base, "boar"), run_name="__main__")
