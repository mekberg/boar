all: rollingcs.so

rollingcs.so: rollingcs.pyx rollsum.c rollsum.h intset.c intset.h setup-cython.py Makefile
	python setup-cython.py build_ext --inplace
