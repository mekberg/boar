#module.o: cdedup.c
#	gcc `/usr/bin/python-config --cflags` cdedup.c 

all: rollsum.o rollingcs.so

rollsum.o: rollsum.c rollsum.h
	gcc -c rollsum.c -o rollsum.o
rollingcs.so: rollingcs.pyx rollsum.o
	python setup-cython.py build_ext --inplace
