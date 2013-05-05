from distutils.core import setup
from distutils.extension import Extension
from Cython.Distutils import build_ext

ext_modules = [Extension("cdedup", 
                         ["cdedup.pyx", "rollsum.c", "intset.c", "circularbuffer.c", "blocksdb.c"],
                         extra_compile_args=["-static", "-O2", "-std=c99", "-Wall"],
                         extra_link_args=["sqlite3.o"],
                         )]

setup(
    name = 'Deduplication module',
    cmdclass = {'build_ext': build_ext},
    ext_modules = ext_modules
    )
