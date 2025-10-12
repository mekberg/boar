PYTHON ?= python3

all: ../cdedup.so

sqlite3.c:
	wget "http://www.sqlite.org/2013/sqlite-amalgamation-3071601.zip" -O sqlite3.zip
	unzip -o sqlite3.zip 
	cp sqlite-amalgamation-3071601/sqlite3.c .
	cp sqlite-amalgamation-3071601/sqlite3.h .
	rm -r sqlite-amalgamation-3071601
	rm sqlite3.zip

sqlite3.o: sqlite3.c sqlite3.h
	gcc -O2 -c -fPIC -Wall sqlite3.c

../cdedup.so: sqlite3.o blocksdb.c blocksdb.h rollsum.c rollsum.h intset.c intset.h circularbuffer.h circularbuffer.c setup-cython.py crc16.h Makefile
	$(PYTHON) setup-cython.py build_ext --inplace
	@# Copy the newest built extension (ABI-specific name) to repo root with a stable name
	@set -e; sofile=$$(ls -t cdedup*.so | head -n1); test -n "$$sofile"; cp -f "$$sofile" ../cdedup.so

