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
from ctypes.util import find_library
from pathlib import Path
from sysconfig import get_config_var, get_paths


SQLITE_VERSION = "3071601"
SQLITE_URL = f"https://www.sqlite.org/2013/sqlite-amalgamation-{SQLITE_VERSION}.zip"


def ensure_sqlite_amalgamation(base_dir):
    """Ensure the SQLite amalgamation exists locally.

    Returns ``True`` if the bundled amalgamation is available (either because it
    already existed or could be downloaded) and ``False`` if it could not be
    obtained.
    """

    sqlite_c = base_dir / "sqlite3.c"
    sqlite_h = base_dir / "sqlite3.h"
    if sqlite_c.exists() and sqlite_h.exists():
        return True

    try:
        from urllib.request import urlopen
    except ImportError:  # pragma: no cover - Python without urllib
        raise SystemExit("urllib is required to download sqlite3 sources")

    print("Fetching SQLite amalgamation...", file=sys.stderr)
    try:
        with urlopen(SQLITE_URL) as response:
            archive_data = response.read()
    except Exception as exc:  # pragma: no cover - network failures
        print(
            "Failed to download the bundled SQLite amalgamation: {}".format(exc),
            file=sys.stderr,
        )
        return False

    with zipfile.ZipFile(io.BytesIO(archive_data)) as zf:
        prefix = f"sqlite-amalgamation-{SQLITE_VERSION}/"
        for filename in ("sqlite3.c", "sqlite3.h"):
            with zf.open(prefix + filename) as source, open(base_dir / filename, "wb") as target:
                target.write(source.read())

    return True


def locate_system_sqlite():
    """Return include/library information for a system SQLite installation.

    The search honours the ``SQLITE_INCLUDE`` and ``SQLITE_LIBDIR`` environment
    variables first.  If those are unset, common include directories as well as
    the Python installation paths are scanned.  When a directory containing a
    ``sqlite3.h`` header is located, the function returns a dictionary with
    ``include_dirs``, ``library_dirs`` and ``libraries`` keys suitable for the
    ``Extension`` constructor.  ``None`` is returned if the header could not be
    found.
    """

    include_candidates = []

    def add_env_paths(varname):
        value = os.environ.get(varname)
        if not value:
            return
        for entry in value.split(os.pathsep):
            entry = entry.strip()
            if entry:
                include_candidates.append(Path(entry))

    add_env_paths("SQLITE_INCLUDE")
    add_env_paths("C_INCLUDE_PATH")
    add_env_paths("CPATH")

    include_paths = get_paths()
    for key in ("include", "platinclude"):
        directory = include_paths.get(key)
        if directory:
            include_candidates.append(Path(directory))

    for key in ("INCLUDEDIR", "CONFINCLUDEPY"):
        directory = get_config_var(key)
        if directory:
            include_candidates.append(Path(directory))

    include_candidates.extend(
        [
            Path(sys.prefix) / "include",
            Path(sys.prefix) / "Include",
            Path("/usr/include"),
            Path("/usr/local/include"),
        ]
    )

    include_dir = None
    for candidate in include_candidates:
        if candidate and (candidate / "sqlite3.h").exists():
            include_dir = candidate
            break

    if include_dir is None:
        return None

    library_dirs = []
    libdir_env = os.environ.get("SQLITE_LIBDIR")
    if libdir_env:
        for entry in libdir_env.split(os.pathsep):
            entry = entry.strip()
            if entry:
                library_dirs.append(entry)

    libraries = []
    explicit_library = os.environ.get("SQLITE_LIBRARY")
    if explicit_library:
        libraries.append(explicit_library)
    else:
        # ``find_library`` is intentionally advisory: on some systems it may
        # return ``None`` even though the linker can resolve ``sqlite3``.  Use
        # it to validate availability but always fall back to the canonical
        # library name expected by the linker.
        library_name = find_library("sqlite3")
        if library_name is None and not library_dirs:
            # No hints were provided and the platform lookup failed; give up so
            # the caller can present a helpful error message.
            return None
        libraries.append("sqlite3")

    return {
        "include_dirs": [str(include_dir)],
        "library_dirs": library_dirs,
        "libraries": libraries,
    }


def compiler_args():
    if os.name == "nt":
        return ["/O2"]
    return ["-O2", "-std=c99", "-Wall"]


def build_extension():
    base_dir = Path(__file__).resolve().parent
    use_amalgamation = ensure_sqlite_amalgamation(base_dir)

    sqlite_config = None
    if not use_amalgamation:
        sqlite_config = locate_system_sqlite()
        if sqlite_config is None:
            raise SystemExit(
                "SQLite amalgamation not available and a system installation could not be located. "
                "Set SQLITE_INCLUDE/SQLITE_LIBDIR to point to the appropriate directories or "
                "run the build with network access to download the amalgamation."
            )

    try:
        from Cython.Build import cythonize
        use_cython = True
    except Exception:
        use_cython = False
        if not (base_dir / "cdedup.c").exists():
            raise SystemExit(
                "Cython is required to build the cdedup extension because the generated "
                "cdedup.c file is missing. Install Cython or build the project in an environment "
                "where it is available to regenerate the C sources."
            )

    sources = [
        base_dir / ("cdedup.pyx" if use_cython else "cdedup.c"),
        base_dir / "rollsum.c",
        base_dir / "intset.c",
        base_dir / "circularbuffer.c",
        base_dir / "blocksdb.c",
    ]

    if use_amalgamation:
        sources.append(base_dir / "sqlite3.c")

    sources = [str(source) for source in sources]

    include_dirs = [str(base_dir)]
    library_dirs = []
    libraries = []

    if sqlite_config is not None:
        include_dirs.extend(sqlite_config.get("include_dirs", []))
        library_dirs.extend(sqlite_config.get("library_dirs", []))
        libraries.extend(sqlite_config.get("libraries", []))

    ext = Extension(
        "cdedup",
        sources,
        extra_compile_args=compiler_args(),
        include_dirs=include_dirs,
        library_dirs=library_dirs,
        libraries=libraries,
        language="c",
    )

    extensions = cythonize([ext]) if use_cython else [ext]

    setup(name="Deduplication module", ext_modules=extensions)


if __name__ == "__main__":  # pragma: no cover - executed via CLI
    build_extension()
