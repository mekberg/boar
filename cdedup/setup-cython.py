from setuptools import Extension, setup

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
