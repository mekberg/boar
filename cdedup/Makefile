all: rollingcs.so

sqlite3.c:
	wget "http://www.sqlite.org/2013/sqlite-amalgamation-3071601.zip" -O sqlite3.zip
	unzip -o sqlite3.zip 
	cp sqlite-amalgamation-3071601/sqlite3.c .
	cp sqlite-amalgamation-3071601/sqlite3.h .
	rm -r sqlite-amalgamation-3071601
	rm sqlite3.zip

sqlite3.o: sqlite3.c sqlite3.h
	gcc -c -fPIC -Wall -lpthread -ldl sqlite3.c 

rollingcs.so: sqlite3.o cdedup.pyx blocksdb.c blocksdb.h rollsum.c rollsum.h intset.c intset.h bitfield.h bitfield.c circularbuffer.h circularbuffer.c setup-cython.py Makefile
	python setup-cython.py build_ext --inplace

