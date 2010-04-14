import os
import sys
import string

def filesize(filename):
    assert os.path.exists(filename)
    size_s = os.popen("wc -c %s|cut -d ' ' -f1" % (filename)).read()
    return int(size_s)

def get_diff_size(filename1, filename2):
    """ Return the patch size required to create filename2 from filename1. """
    try:
        r = os.system("xdelta delta %s %s /tmp/_delta.bin" % (filename1, filename2))
        assert r, "Xdelta failed"
        return filesize("/tmp/_delta.bin")
    finally:
        os.unlink("/tmp/_delta.bin")

def find_relatives(filename, filelist):
    best_size = filesize(filename)
    best = None
    for f in filelist:
        size = get_diff_size(f, filename)
        print "Diff %s -> %s: %s bytes" % (f, filename, size)
        if size < best_size:
            best_size = size
            best = f
    return best

print "Diff size is", get_diff_size("IMG_2601.jpg", "IMG_2601_mod.jpg")

f1 = sys.argv[1]
candidates = sys.argv[2:]

#best = find_relatives("IMG_2601.jpg", ["IMG_2601_mod.jpg"])
best = find_relatives(f1, candidates)
print "Best relative is", best


