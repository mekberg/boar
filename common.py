# -*- coding: utf-8 -*-

# Copyright 2010 Mats Ekberg
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import with_statement

import hashlib
import re
import os
import sys
import platform
import locale
import codecs
import time

from tempfile import TemporaryFile

if sys.version_info >= (2, 6):
    import json
else:
    import simplejson as json

def write_json(filename, obj):
    assert not os.path.exists(filename), "File already exists: " + filename
    with open(filename, "wb") as f:
        json.dump(obj, f, indent = 4)

def read_json(filename):
    with safe_open(filename, "rb") as f:
        return json.load(f)

""" This file contains code that is generally useful, without being
specific for any project """

def is_md5sum(str):
    try:
        return re.match("^[a-f0-9]{32}$", str) != None    
    except TypeError:
        return False

def is_sha256(str):
    try:
        return re.match("^[a-f0-9]{64}$", str) != None    
    except TypeError:
        return False

assert is_md5sum("7df642b2ff939fa4ba27a3eb4009ca67")

def warn(s):
    sys.stderr.write("WARNING: ")
    sys.stderr.write(s)
    sys.stderr.write("\n")

def notice(s):
    sys.stderr.write("NOTICE: ")
    sys.stderr.write(s)
    sys.stderr.write("\n")

def read_file(path):
    """Reads and returns the contents of the given filename."""
    with safe_open(path) as f:
        return f.read()

_file_reader_sum = 0
def file_reader(f, start = 0, end = None, blocksize = 2 ** 16):
    """Accepts a file object and yields the specified part of
    the file as a sequence of blocks with length <= blocksize."""
    global _file_reader_sum
    f.seek(0, os.SEEK_END)
    real_end = f.tell()
    assert end == None or end <= real_end, "Can't read past end of file"
    f.seek(start)
    if end == None:
        end = real_end
    bytes_left = end - start
    while bytes_left > 0:
        data = f.read(min(bytes_left, blocksize))
        assert data != "", "Unexpected failed read"
        bytes_left -= len(data)
        _file_reader_sum += len(data)
        yield data

def safe_open(path, flags = "rb"):
    """Returns a read-only file handle for the given path."""
    assert flags in ("rb", "r"), "only modes 'r' or 'rb' allowed"
    return open(path, "rb")

def md5sum(data):
    m = hashlib.md5()
    m.update(data)
    return m.hexdigest()

def md5sum_fileobj(f, start = 0, end = None):
    """Accepts a file object and returns the md5sum."""
    return checksum_fileobj(f, ["md5"], start, end)[0]

def md5sum_file(f, start = 0, end = None):
    """Accepts a filename or a file object and returns the md5sum."""
    return checksum_file(f, ["md5"], start, end)[0]

def checksum_fileobj(f, checksum_names, start = 0, end = None):
    """Accepts a file object and returns one or more checksums. The
    desired checksums are specified in a list by name in the
    'checksum_names' argument."""
    checksummers = []
    for name in checksum_names:
        assert name in ("md5", "sha256", "sha512")
        checksummers.append(eval("hashlib.%s()" % name))
    for block in file_reader(f, start, end):
        assert block != "", "Got an empty read"
        for m in checksummers:
            m.update(block)
    result = []
    for m in checksummers:
        result.append(m.hexdigest())
    return result

def checksum_file(f, checksum_names, start = 0, end = None):
    """Accepts a filename or a file object and returns one or more
    checksums. The desired checksums are specified in a list by name
    in the 'checksum_names' argument."""
    assert f, "File must not be None"
    if isinstance(f, basestring):
        with safe_open(f, "rb") as fobj:
            return checksum_fileobj(fobj, checksum_names, start, end)
    return checksum_fileobj(f, checksum_names, start, end)

def copy_file(source, destination, start = 0, end = None, expected_md5sum = None):
    assert os.path.exists(source), "Source doesn't exist"
    assert not os.path.exists(destination), "Destination already exist"
    m = hashlib.md5()
    with safe_open(source, "rb") as sobj:
        reader = file_reader(sobj, start, end)
        with open(destination, "wb") as dobj:
            for block in reader:
                if expected_md5sum:
                    m.update(block)
                dobj.write(block)
    if expected_md5sum:
        assert m.hexdigest() == expected_md5sum, \
            "Copied file did not have expected md5sum"

def move_file(source, destination, mkdirs = False):
    assert not os.path.exists(destination)
    dirname = os.path.dirname(destination)
    if mkdirs and not os.path.exists(dirname):
        os.makedirs(dirname)
    os.rename(source, destination)

def create_file(destination, content, tmp_suffix = ".tmp"):
    """Write the given content to a new file at the given path. The
    file must not exist before. The contents will first be written to
    a temporary file in the destination directory, with the given
    suffix, and then moved to its destination. The suffix file may
    exist and will in that case be overwritten and lost."""
    assert not os.path.exists(destination)
    tmpfile = destination + tmp_suffix
    with open(tmpfile, "w") as f:
        f.write(content)
    os.rename(tmpfile, destination)

def replace_file(destination, content, tmp_suffix = ".tmp"):
    """Write the given content to a possibly existing file at the
    given path. The contents will first be written to a temporary file
    in the destination directory, with the given suffix, and then
    moved to its destination. The suffix file may exist and will in
    that case be overwritten and lost. Note that this operation is not
    atomic, the destination file may just be deleted if the operation
    fails half-way."""
    tmpfile = destination + tmp_suffix
    with open(tmpfile, "w") as f:
        f.write(content)
    if os.path.exists(destination):
        os.remove(destination)
    os.rename(tmpfile, destination)

def split_file(source, dest_dir, cut_positions, want_piece = None):
    """'Cuts' is a list of positions where to split the source
    file. All cuts must be within the bounds of the file. Cuts must
    not occur at the very start or end of the file. If the cut is at
    position n, the first part will end at byte n-1, and the second
    part will begin with byte n as the first byte. The results will be
    written to the dest_dir. Each individual file will be named by
    its' md5sum. The 'want_piece' is an optional function to control
    if a given part shall be written to disk or not. The function must
    accept a single argument with the md5sum of the piece given as a
    string, and must return True if the piece should be written to the
    destination dir. This function returns a list of the pieces in the
    order they should be concatenated to recreate the original file."""

    cuts = cut_positions[:]
    assert len(set(cuts)) == len(cuts), "Duplicate entry in cut list"
    assert len(cuts) >= 1, "Empty cuts not allowed"
    source_size = os.path.getsize(source)
    assert max(cuts) < source_size and min(cuts) > 0, "Cut for %s out of range: %s" % (blob, cuts)
    cuts.append(0) # Always have an implicit cut starting at 0
    cuts.append(source_size) # Always have an implicit cut ending at source_size
    cuts.sort()
    added_blobs = []
    start = cuts.pop(0)
    while len(cuts) > 0:
        end = cuts.pop(0)
        checksum = md5sum_file(source, start, end)
        if not want_piece(checksum) or checksum in added_blobs:
            added_blobs.append(checksum)
            start = end
            continue
        added_blobs.append(checksum)
        destination = os.path.join(dest_dir, checksum)
        copy_file(source, destination, start, end, checksum)
        start = end
    return added_blobs

def convert_win_path_to_unix(path):
    """ Converts "C:\\dir\\file.txt" to "/dir/file.txt". 
        Has no effect on unix style paths. """
    assert isinstance(path, unicode)
    nodrive = os.path.splitdrive(path)[1]
    result = nodrive.replace("\\", "/")
    #print "convert_win_path_to_unix: " + path + " => " + result
    return result

def is_windows_path(path):
    return "\\" in path

def get_relative_path(p):
    """ Normalizes the path to unix format and then removes drive letters
    and/or slashes from the given path """
    p = convert_win_path_to_unix(p)
    while True:
        if p.startswith("/"):
            p = p[1:]
        elif p.startswith("./"):
            p = p[2:]
        else:
            return p

# This method avoids an infinite loop when add_path_offset() and
# strip_path_offset() verfies the results of each other.
def __add_path_offset(offset, p):
    return offset + "/" + p

def add_path_offset(offset, p):
    result = __add_path_offset(offset, p)
    assert strip_path_offset(offset, result) == p
    return result

def strip_path_offset(offset, p):
    """ Removes the initial part of pathname p that is identical to
    the given offset. Example: strip_path_offset("myfiles",
    "myfiles/dir1/file.txt") => "dir1/file.txt" """
    # TODO: For our purposes, this function really is a dumber version
    # of my_relpath(). One should replace the other.
    if offset == "":
        return p
    assert not offset.endswith("/"), "Offset must be given without ending slash. Was: "+offset
    assert p.startswith(offset), "'%s' does not begin with offset '%s'" % (p, offset)
    assert p[len(offset)] == "/", "Offset was: "+offset+" Path was: "+p
    result = p[len(offset)+1:]
    assert __add_path_offset(offset, result) == p
    return result

def is_child_path(parent, child):
    assert type(parent) == unicode
    assert type(child) == unicode
    if parent == "":
        return True
    result = child.startswith(parent + "/")
    #print "is_child_path('%s', '%s') => %s" % (parent, child, result)
    return result

def split_path_from_start(path):
    """Works like os.path.split(), but splits from the beginning of
    the path instead. /var/tmp/junk returns ("var",
    "tmp/junk"). Windows style paths will be converted and returned
    unix-style."""
    assert type(path) == unicode
    path = convert_win_path_to_unix(path)
    path = path.lstrip("/")
    if "/" in path:
        pieces = path.split("/")
    else:
        pieces = [path]
    head, tail = pieces[0], u"/".join(pieces[1:])
    assert type(head) == unicode
    assert type(tail) == unicode
    return head, tail

assert split_path_from_start(u"junk") == ("junk", "")
assert split_path_from_start(u"") == ("", "")
assert split_path_from_start(u"/var/tmp/junk") == ("var", "tmp/junk")
assert split_path_from_start(u"var\\tmp\\junk") == ("var", "tmp/junk")

import os.path as posixpath
from os.path import curdir, sep, pardir, join
# Python 2.5 compatible relpath(), Based on James Gardner's relpath
# function.
# http://www.saltycrane.com/blog/2010/03/ospathrelpath-source-code-python-25/
def my_relpath(path, start=curdir):
    """Return a relative version of a path"""
    assert os.path.isabs(path)
    if not path:
        raise ValueError("no path specified")
    assert isinstance(path, unicode)
    assert isinstance(start, unicode)
    absstart = posixpath.abspath(start)
    abspath = posixpath.abspath(path)
    if absstart[-1] != os.path.sep:
        absstart += os.path.sep
    assert abspath.startswith(absstart), abspath + " " + absstart    
    return abspath[len(absstart):]

def open_raw(filename):
    """Try to read the file in such a way that the system file cache
    is not used."""
    # TODO: implement
    return open(filename, "rb")
    # This does not work for some reason:
    # try:
    #     fd = os.open(filename, os.O_DIRECT | os.O_RDONLY, 10000000)
    #     print "Successfully using O_DIRECT"
    #     return os.fdopen(fd, "rb", 10000000)
    # except Exception, e:
    #     print "Failed using O_DIRECT", e
    #     return open(filename, "rb")

def get_tree(root, skip = [], absolute_paths = False):
    """ Returns a simple list of all the files under the given root
    directory. Any files or directories given in the skip argument
    will not be returned or scanned."""
    assert isinstance(root, unicode) # type affects os.path.walk callback args
    def visitor(out_list, dirname, names):
        for file_to_skip in skip:
            if file_to_skip in names:
                names.remove(file_to_skip)
        for name in names:
            assert type(name) == unicode, "All filenames should be unicode"
            try:
                fullpath = os.path.join(dirname, name)
            except:
                print "Failed on file:", dirname, name
                raise
            if not os.path.isdir(fullpath):
                out_list.append(fullpath)
    all_files = []
    os.path.walk(root, visitor, all_files)
    remove_rootpath = lambda fn: convert_win_path_to_unix(my_relpath(fn, root))
    if not absolute_paths:
        all_files = map(remove_rootpath, all_files)
    else:
        all_files = map(convert_win_path_to_unix, all_files)
    for f in all_files:
        assert not is_windows_path(f), "Was:" + f
        assert not ".." in f.split("/"), "Was:" + f
        assert not "\\" in f, "Was:" + f
    return all_files



class FileMutex:
    class MutexLocked(Exception):
        def __init__(self, mutex_name, mutex_file):
            self.mutex_name = mutex_name
            self.mutex_file = mutex_file
            self.value = "Mutex '%s' was already locked. Lockfile is '%s'" % (mutex_name, mutex_file)

        def __str__(self):
            return self.value

    def __init__(self, mutex_dir, mutex_name):
        assert isinstance(mutex_name, basestring)
        self.mutex_dir = mutex_dir
        self.mutex_name = mutex_name
        self.mutex_id = md5sum(mutex_name.encode("utf-8"))
        self.mutex_file = os.path.join(self.mutex_dir, "mutex-" + self.mutex_id)
        self.locked = False
    
    def lock(self):
        assert not self.locked, "Tried to lock a mutex twice"
        try:
            os.mkdir(self.mutex_file)
            self.locked = True
        except OSError, e:
            if e.errno != 17: # errno 17 = directory already exists
                raise
            raise FileMutex.MutexLocked(self.mutex_name, self.mutex_file)

    def lock_with_timeout(self, timeout):
        assert not self.locked, "Tried to lock a mutex twice"
        t0 = time.time()
        while True:
            try:
                self.lock()
                break
            except FileMutex.MutexLocked:                
                if time.time() - t0 > timeout:
                    break
                time.sleep(1)
        if not self.locked:
            raise FileMutex.MutexLocked(self.mutex_name, self.mutex_file)

    def is_locked(self):
        return self.locked
    
    def release(self):
        assert self.locked, "Tried to release unlocked mutex"
        try:
            os.rmdir(self.mutex_file)
            self.locked = False
        except OSError:
            print "Warning: could not remove lockfile", self.mutex_file

    def __del__(self):
        if self.locked:
            print "Warning: lockfile %s was forgotten. Cleaning up..." % self.mutex_name
            self.release()

def tounicode(s):
    """Decodes a string from the system default encoding to
    unicode. Unicode strings are returned unchanged. None argument
    returns None result."""
    if s == None:
        return None
    if isinstance(s, unicode):
        return s
    s = s.decode(locale.getpreferredencoding())
    assert type(s) == unicode
    return s

class StreamEncoder:
    """ Wraps an output stream (typically sys.stdout) and encodes all
    written strings according to the current preferred encoding, with
    configurable error handling. Using errors = "strict" will yield
    identical behaviour to original sys.stdout."""

    def __init__(self, stream, errors = "backslashreplace"):
        assert errors in ("strict", "replace", "ignore", "backslashreplace")
        self.errors = errors
        self.stream = stream
        self.codec_name = locale.getpreferredencoding()

    def write(self, s):
        if type(s) != unicode:
            self.stream.write(s)
            return
        encoded_s = s.encode(self.codec_name, self.errors)
        self.stream.write(encoded_s)

    def close(self):
        self.stream.close()

    def __enter__(self):
        """ Support for the 'with' statement """
        return self

    def __exit__(self, type, value, traceback):
        """ Support for the 'with' statement """
        self.close()

def dir_exists(path):
    return os.path.exists(path) and os.path.isdir(path)


class RateLimiter:
    """This class makes it easy to perform some action only when a
    certain time has passed. The maxrate parameter is given in Hz and
    may be a float. The first call to ready() will always return
    True, and then the timer starts ticking."""

    def __init__(self, maxrate):
        self.min_period = 1.0 / maxrate
        self.last_trig = 0.0
    
    def ready(self):
        now = time.time()
        if now - self.last_trig >= self.min_period:
            self.last_trig = now
            return True
        return False

def isWritable(path):
    """Performs a write test to check if it is possible to create new
    files and directories under the given path. The given path must
    exist and be a directory."""
    assert os.path.exists(path)
    assert os.path.isdir(path)
    try:
        with TemporaryFile(dir=path):
            pass
    except OSError, e:
        return False
    return True
