import importlib
import importlib.util
import subprocess
import sys


def _load_setuptools_components():
    if importlib.util.find_spec("setuptools") is None:
        ensurepip_spec = importlib.util.find_spec("ensurepip")
        if ensurepip_spec is not None:
            ensurepip = importlib.import_module("ensurepip")
            try:
                ensurepip.bootstrap()
            except Exception:
                pass
        try:
            subprocess.check_call(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "--upgrade",
                    "pip",
                    "setuptools",
                    "wheel",
                ]
            )
        except Exception as exc:  # pragma: no cover - fatal during packaging
            raise ModuleNotFoundError(
                "setuptools is required but could not be installed automatically"
            ) from exc
    setuptools = importlib.import_module("setuptools")
    return setuptools.Extension, setuptools.setup


Extension, setup = _load_setuptools_components()

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
]

ext = Extension(
    "cdedup",
    sources,
    extra_compile_args=["-O2", "-std=c99", "-Wall"],
    extra_objects=["sqlite3.o"],
    language="c",
)

extensions = cythonize([ext]) if use_cython else [ext]

setup(name="Deduplication module", ext_modules=extensions)
