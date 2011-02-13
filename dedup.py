import os
from common import *
import string

def file_prefix_md5sum(filename, prefix_size):
    assert os.path.getsize(filename) >= prefix_size
    return md5sum_file(filename, 0, prefix_size)

def file_suffix_md5sum(filename, suffix_size):
    filesize = os.path.getsize(filename)
    assert filesize >= suffix_size
    return md5sum_file(filename, filesize - suffix_size, filesize)

def groupBy(files, size, md5summer):
    groups = {}
    n = 0
    for filename in files:
        print n, len(files)
        n+=1
        filesize = os.path.getsize(filename)
        if filesize < size:
            continue
        md5 = md5summer(filename, size)
        group = groups.get(md5, [])
        group.append(filename)
        groups[md5] = group
    return groups.values()

def findIdenticalSuffix(file1, file2):
    blocksize = 4096
    fsize1, fsize2 = os.path.getsize(file1), os.path.getsize(file2)
    remaining = min(fsize1, fsize2)
    identical = 0
    while remaining > 0:
        s1 = md5sum_file(file1, fsize1 - identical - blocksize, fsize1 - identical)
        s2 = md5sum_file(file2, fsize2 - identical - blocksize, fsize2 - identical)
        if s1 != s2:
            break
        identical += blocksize
        remaining -= blocksize
        print remaining
    return identical

def main():
    file1, file2 = sys.argv[1:]
    print findIdenticalSuffix(file1, file2)


def main_old():
    if sys.argv[2] == "-":
        files = map(string.strip, sys.stdin.readlines())
    else:
        files = sys.argv[2:]

    files = [ filename for filename in files if os.path.getsize(filename) > 1000000 ]

    size = 4096
    if sys.argv[1] == "prefix":
        groups = groupBy(files, size, file_prefix_md5sum)
    elif sys.argv[1] == "suffix":
        groups = groupBy(files, size, file_suffix_md5sum)
    else:
        assert False

    for g in groups:
        if len(g) > 1:
            for f in g:                
                print f

main()
