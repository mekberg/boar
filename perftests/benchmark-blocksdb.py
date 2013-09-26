from deduplication import BlocksDB
import tempfile
import random
from time import time
import os

#tmpfile = tempfile.NamedTemporaryFile(dir="/tmp")
filename = "/gigant/tmp/benchmark.db"
#filename = tmpfile.name
#print "Using db", tmpfile.name
blocksize = 2**16
db = BlocksDB(filename, blocksize)
#db = BlockLocationsDB(blocksize, ":memory:")
#db = BlockLocationsDB(blocksize, "/gigant/tmp/benchmark.db")

#for n in range(0, random.randrange(20000)):
"""
for c in range(0, 100):
    db.begin()
    for n in range(0, 100000):
        db.add_block(blob = "ablob".zfill(32),
                     offset = 0,
                     md5 = str(random.randrange(2**64)).zfill(32))
        db.add_rolling(random.randrange(2**64))
    db.commit()
    print c
"""
#
# 10000 block -> ca 500 MB per commit
# 1000 commits, repot upp till 500 GB
def main1():
    for c in range(0, 1000):
        t0 = time()
        db.begin()
        #for n in range(0, random.randrange(20000)):
        for n in range(0, 10000):
            db.add_block(blob = str(c).zfill(32), 
                         offset = n*blocksize, 
                         md5 = str(random.randrange(2**64)).zfill(32))
            db.add_rolling(random.randrange(2**64))
        db.commit()
        print c, round(time() - t0, 2), os.path.getsize(filename)


def main2():
    import cPickle
    count = 0
    pickler = cPickle.Pickler(open("/gigant/tmp/largedb.pickle", "wb"))
    for row in db.get_all_blocks():
        pickler.dump(row)
        if count % 100000 == 0:
            print count
            pickler.clear_memo()
        count += 1
    #s = set(db.get_all_blocks())

def main3():
    import shelve
    count = 0
    sh = shelve.open("/gigant/tmp/largedb.shelve")
    for row in db.get_all_blocks():
        sh[str(row[2])] = row
        if count % 100000 == 0:
            print count
        count += 1
    #s = set(db.get_all_blocks())

main1()
