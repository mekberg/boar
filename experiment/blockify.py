import os, sys, string, hashlib

def md5sum(data):
    m = hashlib.md5()
    m.update(data)
    return m.hexdigest()

separator = "ab"

def split(data, sep, minlimit = 50000):
    parts = string.split(data, sep)    
    i = 0
    while i < len(parts) - 1:
        if len(parts[i]) < minlimit or len(parts[i+1]) < minlimit:
            parts[i:i+2] = [parts[i]  + sep + parts[i+1]]
        else:
            i += 1
    return parts

def main():
    filename =sys.argv[1]
    filedata = open(filename, "r").read()
    parts = split(filedata, separator)
    print "Data was split into", len(parts), "parts"
    for p in parts:
        print md5sum(p), len(p)
main()
