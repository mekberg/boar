all: rollingcs.so

rollingcs.so: rollingcs.pyx blocksdb.c blocksdb.h rollsum.c rollsum.h intset.c intset.h bitfield.h bitfield.c circularbuffer.h circularbuffer.c setup-cython.py Makefile
	python setup-cython.py build_ext --inplace

