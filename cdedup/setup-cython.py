try:
    from setuptools import Extension, setup
except ImportError:  # pragma: no cover - allow building without setuptools on legacy Python
    try:
        from distutils.core import setup  # type: ignore[attr-defined]
        from distutils.extension import Extension  # type: ignore[attr-defined]
    except ImportError as exc:  # Python 3.12+ without setuptools present
        raise SystemExit("setuptools is required to build the cdedup extension") from exc

import io
import os
import sys
import zipfile
from pathlib import Path


SQLITE_VERSION = "3071601"
SQLITE_URL = f"https://www.sqlite.org/2013/sqlite-amalgamation-{SQLITE_VERSION}.zip"


def ensure_sqlite_amalgamation(base_dir):
    """Download the SQLite amalgamation used by the extension if missing."""

    sqlite_c = base_dir / "sqlite3.c"
    sqlite_h = base_dir / "sqlite3.h"
    if sqlite_c.exists() and sqlite_h.exists():
        return

    try:
        from urllib.request import urlopen
    except ImportError:  # pragma: no cover - Python without urllib
        raise SystemExit("urllib is required to download sqlite3 sources")

    print("Fetching SQLite amalgamation...", file=sys.stderr)
    try:
        with urlopen(SQLITE_URL) as response:
            archive_data = response.read()
    except Exception as exc:  # pragma: no cover - network failures
        raise SystemExit(f"Failed to download SQLite amalgamation: {exc}") from exc

    with zipfile.ZipFile(io.BytesIO(archive_data)) as zf:
        prefix = f"sqlite-amalgamation-{SQLITE_VERSION}/"
        for filename in ("sqlite3.c", "sqlite3.h"):
            with zf.open(prefix + filename) as source, open(base_dir / filename, "wb") as target:
                target.write(source.read())


def compiler_args():
    if os.name == "nt":
        return ["/O2"]
    return ["-O2", "-std=c99", "-Wall"]


def build_extension():
    base_dir = Path(__file__).resolve().parent
    ensure_sqlite_amalgamation(base_dir)

    try:
        from Cython.Build import cythonize
        use_cython = True
    except Exception:
        use_cython = False

    sources = [
        "cdedup.pyx" if use_cython else "cdedup.c",
        "rollsum.c",
        "intset.c",
        "circularbuffer.c",
        "blocksdb.c",
        "sqlite3.c",
    ]

    ext = Extension(
        "cdedup",
        sources,
        extra_compile_args=compiler_args(),
        include_dirs=[str(base_dir)],
        language="c",
    )

    extensions = cythonize([ext]) if use_cython else [ext]

    setup(name="Deduplication module", ext_modules=extensions)


if __name__ == "__main__":  # pragma: no cover - executed via CLI
    build_extension()
