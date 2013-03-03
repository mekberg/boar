from distutils.core import setup
from distutils.extension import Extension
from Cython.Distutils import build_ext

ext_modules = [Extension("rollingcs", 
                         ["rollingcs.pyx", "rollsum.c", "intset.c", "bitfield.c", "circularbuffer.c"],
                         extra_compile_args=["-O9", "-std=c99"],
                         )]

setup(
    name = 'Rolling checksum',
    cmdclass = {'build_ext': build_ext},
    ext_modules = ext_modules
    )
