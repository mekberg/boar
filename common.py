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
import textwrap

from tempfile import TemporaryFile
from threading import current_thread

try: 
    # Simplejson can be a lot faster, but has some odd optimization
    # that makes the result mix str and unicode instances. By
    # converting the argument string into unicode
    import simplejson as json
    original_loads = json.loads
    def unicode_loads(s, *args, **kw):
        if type(s) == str:
            s = unicode(s, "utf-8")
        return original_loads(s, *args, **kw)
    json.loads = unicode_loads
except ImportError: 
    import json

del json.load # Let's not use this

def get_json_module():
    return json

# Something like sys.maxsize, but works pre-2.6
VERY_LARGE_NUMBER = 9223372036854775807L

def verify_assert():
    try:
        assert False
        raise Exception("This module requires asserts to be enabled (don't use python -O flag)")
    except AssertionError:
        # Asserts are enabled
        pass

verify_assert() # This module uses assert to check for external conditions.

def dumps_json(obj):
    return json.dumps(obj, indent = 4)

def write_json(filename, obj):
    assert not os.path.exists(filename), "File already exists: " + filename
    data = dumps_json(obj)
    with StrictFileWriter(filename, md5sum(data), len(data)) as f:
        f.write(data)

def read_json(filename):
    with safe_open(filename, "rb") as f:
        return json.loads(f.read())

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

def prefixwrap(prefix, text, rowlen = 80):
    rows = textwrap.wrap(text, width = rowlen - len(prefix))
    result = [prefix + rows.pop(0)]
    while rows:
        result.append(" " * len(prefix) + rows.pop(0))
    return result

def prefixprint(prefix, text, stream = None):
    if stream == None:
        stream = sys.stderr
    for row in prefixwrap(prefix, text):
        stream.write(row)
        stream.write("\n")

def error(s, stream = None):
    prefixprint("ERROR: ", s, stream)

def warn(s, stream = None):
    prefixprint("WARNING: ", s, stream)

def notice(s, stream = None):
    prefixprint("NOTICE: ", s, stream)

def read_file(path, expected_md5 = None):
    """Reads and returns the contents of the given filename. If
    expected_md5 is given, the contents of the file will be verified
    before they are returned. If there is a mismatch, a
    ContentViolation error will be raised."""
    with safe_open(path) as f:
        data = f.read()
    if expected_md5 and md5sum(data) != expected_md5:
        raise ContentViolation("File '%s' did not have expected checksum '%s'" % (path, expected_md5))
    return data

def parse_md5sum(text):
    """Expects a sting containing a classic md5sum.exe output format,
    and returns the data on the form [(md5, filename), ...]. Note that
    the data must be utf-8 encoded, or an UnicodeDecodeError will be
    raised. One notable source of such non-utf-8 files is md5sum.exe
    on Windows."""
    result = []
    for line in text.splitlines():
        line = line.rstrip("\r\n")
        filename = line[34:]
        filename = filename.decode("utf-8")
        result.append((line[0:32], convert_win_path_to_unix(filename)))
    return result

def read_md5sum(path, expected_md5 = None):
    """Reads a classic md5sum.exe output file and returns the data on
    the form [(md5, filename), ...]. Note that the data must be utf-8 encoded,
    or an UnicodeDecodeError will be raised. One notable source of such
    non-utf-8 files is md5sum.exe on Windows."""
    data = read_file(path, expected_md5)
    if data.startswith('\xef\xbb\xbf'):
        data = data[3:] # Remove unicode BOM
    return parse_md5sum(data)

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
        if data == "":
            raise IOError("Unexpected failed read")
        bytes_left -= len(data)
        _file_reader_sum += len(data)
        yield data

def safe_open(path, flags = "rb"):
    """Returns a read-only file handle for the given path."""
    if flags != "rb":
        raise ValueError("only mode 'rb' allowed")
    return open(path, "rb")

def md5sum(data):
    m = hashlib.md5()
    m.update(data)
    return m.hexdigest()

def sha256(data):
    m = hashlib.sha256()
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
        summer = hashlib.__dict__[name]()
        checksummers.append(summer)
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
    assert not os.path.exists(destination), "File already exists: %s" % destination
    tmpfile = destination + tmp_suffix
    with StrictFileWriter(tmpfile, md5sum(content), len(content)) as f:
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
    with StrictFileWriter(tmpfile, md5sum(content), len(content)) as f:
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
def __add_path_offset(offset, p, separator="/"):
    assert separator in ("/", "\\")
    return offset + separator + p

def add_path_offset(offset, p, separator="/"):
    assert separator in ("/", "\\")
    result = __add_path_offset(offset, p, separator)
    assert strip_path_offset(offset, result, separator) == p
    return result

def strip_path_offset(offset, path, separator="/"):
    """ Removes the initial part of pathname 'path' that is identical to
    the given 'offset'. Example: strip_path_offset("myfiles",
    "myfiles/dir1/file.txt") => "dir1/file.txt" """
    # TODO: For our purposes, this function really is a dumber version
    # of my_relpath(). One should replace the other.
    if offset == "":
        return path
    if offset == path:
        return u""
    assert separator in ("/", "\\")
    assert not offset.endswith(separator), "Offset must be given without ending slash. Was: "+offset
    assert is_child_path(offset, path, separator), "Path %s is not a child of offset %s" % (path, offset)
    result = path[len(offset)+1:]
    assert __add_path_offset(offset, result, separator) == path
    return result

def is_child_path(parent, child, separator="/"):    
    # We don't want any implicit conversions to unicode. That might
    # cause decoding errors.
    assert type(parent) == type(child)

    assert separator in ("/", "\\")
    if parent == "":
        return True
    result = child.startswith(parent + separator)
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

def posix_path_join(*parts):
    """This function works similar to os.path.join() on posix
    platforms (using "/" as separator)."""
    parts = [p for p in parts if p != ""]
    return "/".join(parts)

assert posix_path_join("", "/tmp") == "/tmp"
assert posix_path_join("", "tmp") == "tmp"
assert posix_path_join("a", "b") == "a/b"

# Python 2.5 compatible relpath(), Based on James Gardner's relpath
# function.
# http://www.saltycrane.com/blog/2010/03/ospathrelpath-source-code-python-25/
def my_relpath(path, start=os.path.curdir):
    """Return a relative version of a path"""
    assert os.path.isabs(path)
    if not path:
        raise ValueError("no path specified")
    assert isinstance(path, unicode)
    assert isinstance(start, unicode)
    absstart = os.path.abspath(start)
    abspath = os.path.abspath(path)
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

class __DummyProgressPrinter:
    """Dummy progress printer for use in get_tree"""
    def update(self): pass
    def finished(self): pass

def get_tree(root, skip = [], absolute_paths = False, progress_printer = None):
    """ Returns a simple list of all the files under the given root
    directory. Any files or directories given in the skip argument
    will not be returned or scanned.

    The progress printer, if given, must be an object with two methods
    "update()" and "finished()", neither accepting any
    parameters. Update will be called once for every file seen, and
    then finished will be called.
    """
    assert isinstance(root, unicode) # type affects os.path.walk callback args
    assert type(skip) == type([]), "skip list must be a list"

    if not progress_printer:
        progress_printer = __DummyProgressPrinter()

    if not absolute_paths:
        post_process = lambda fn: convert_win_path_to_unix(my_relpath(fn, root))
    else:
        post_process = convert_win_path_to_unix

    def visitor(out_list, dirname, names):
        for file_to_skip in skip:
            if file_to_skip in names:
                names.remove(file_to_skip)
        for name in names:
            assert type(name) == unicode, "All filenames should be unicode"
            try:
                fullpath = os.path.join(dirname, name)
                unc_path = unc_abspath(fullpath)
                assert os.path.exists(unc_path), "File was removed during scan"
                if os.path.isdir(unc_path):
                    continue
            except OSError:
                print "Failed on file:", dirname, name
                raise

            f = post_process(fullpath)
            assert not is_windows_path(f), "Was:" + f
            assert not ".." in f.split("/"), "Was:" + f
            assert not "\\" in f, "Was:" + f
            out_list.append(f)
            progress_printer.update()

    all_files = []
    os.path.walk(root, visitor, all_files)
    progress_printer.finished()
    return all_files

class FileMutex:
    """ The purpose of this class is to protect a shared resource from
    other processes. It accomplishes this by using the atomicity of
    the mkdir system call.

    This class allows any number of concurrent locks within a single
    process, and hence does not work as a mutex in that
    context. Access from multiple threads is not supported and will
    cause an assertion error. The mutex must only be accessed from the
    same thread that created it.
    """

    class MutexLocked(Exception):
        def __init__(self, mutex_name, mutex_file):
            self.mutex_name = mutex_name
            self.mutex_file = mutex_file
            self.value = "Mutex '%s' was already locked. Lockfile is '%s'" % (mutex_name, mutex_file)

        def __str__(self):
            return self.value

    def __init__(self, mutex_dir, mutex_name):
        """The mutex will be created in the mutex_dir directory, which
        must exist and be writable. The actual name of the mutex will
        be a hash of the mutex_name, and therefore the mutex_name does
        not need to be a valid filename.
        """
        assert isinstance(mutex_name, basestring)
        self.owner_thread = current_thread()
        self.mutex_name = mutex_name
        self.mutex_id = md5sum(mutex_name.encode("utf-8"))
        self.mutex_file = os.path.join(mutex_dir, "mutex-" + self.mutex_id)
        self.owner_id = md5sum(str(time.time()) + str(os.getpid())) + "-" + str(os.getpid())
        self.mutex_owner_file = os.path.join(self.mutex_file, self.owner_id)
        self.lock_levels = 0
    
    def lock(self):
        """ Lock the mutex. Throws a FileMutex.MutexLocked exception
        if the lock is already locked by another process. If the lock
        is free, it will be acquired.
        """
        assert self.owner_thread.ident == current_thread().ident, "FileMutex does not support threading"
        if self.is_locked():
            assert os.path.exists(self.mutex_owner_file)
            # This thread already owns the lock
            self.lock_levels += 1
            return
        try:
            os.mkdir(self.mutex_file)
            with open(self.mutex_owner_file, "w"): pass
            self.lock_levels += 1
        except OSError, e:
            if e.errno != 17: # errno 17 = directory already exists
                raise
            #lockpid = int(os.listdir(self.mutex_file)[0].split("-")[1])
            #print "Lock already taken by", lockpid, "(not necessarily a local pid)"
            raise FileMutex.MutexLocked(self.mutex_name, self.mutex_file)

    def lock_with_timeout(self, timeout):
        """ Lock the mutex. If the lock is already taken by another
        process, it will be retried until 'timeout' seconds have
        passed. If the lock is still not available, a
        FileMutex.MutexLocked exception is thrown.
        """
        assert self.owner_thread.ident == current_thread().ident, "FileMutex does not support threading" + str(self.owner_thread.ident) + " " + str(current_thread().ident)
        if self.is_locked() and os.path.exists(self.mutex_owner_file):
            # This thread already owns the lock
            self.lock_levels += 1
            return
        t0 = time.time()
        while True:
            try:
                self.lock()
                break
            except FileMutex.MutexLocked:                
                if time.time() - t0 > timeout:
                    break
                time.sleep(1)
        if not self.is_locked():
            raise FileMutex.MutexLocked(self.mutex_name, self.mutex_file)

    def is_locked(self):
        """ Returns True iff the lock is acquired by the current process. """
        return self.lock_levels > 0
    
    def release(self):
        """ Releases the lock. Actual mutex release will happen only
        when all users in the current process has released their
        locks. If release is called when the mutex is not locked, an
        assertion error will be raised."""
        assert self.owner_thread.ident == current_thread().ident, "FileMutex does not support threading"
        assert self.is_locked(), "Tried to release unlocked mutex"
        self.lock_levels -= 1
        if self.lock_levels > 0:
            return
        try:
            os.unlink(self.mutex_owner_file)
            os.rmdir(self.mutex_file)
        except OSError:
            print "Warning: could not remove lockfile", self.mutex_file

    def __del__(self):
        if self.is_locked():
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

def dedicated_stdout():
    """ This function replaces the sys.stdout with sys.stderr and
    returns sys.stdout so that the caller gets exclusive
    access. (unless someone else has made a local copy). This function
    is aware of StreamEncoder and will make sure that nothing has been
    written to stdout at the time of the call, otherwise an
    AssertionError will be raised. This function will always return
    the original sys.stdout, even if it has been wrapped in a
    StreamEncoder."""
    if isinstance(sys.stdout, StreamEncoder):
        assert sys.stdout.bytecount == 0, "Cannot dedicate stdout, some data has already been written"
        real_stdout = sys.stdout.stream
    else:
        real_stdout = sys.stdout
    sys.stdout = sys.stderr
    return real_stdout

def encoded_stdout():
    """Returns the sys.stdout stream wrapped in a StreamEncoder. Makes
    sure that there is no accidential nesting of StreamEncoder due to
    globally replacing sys.stdout with a wrapped version."""
    if isinstance(sys.stdout, StreamEncoder):
        return sys.stdout
    else:
        return StreamEncoder(sys.stdout)

class StreamEncoder:
    """ Wraps an output stream (typically sys.stdout) and encodes all
    written strings according to the current preferred encoding, with
    configurable error handling. Using errors = "strict" will yield
    identical behaviour to original sys.stdout."""

    def __init__(self, stream, errors = "backslashreplace"):
        assert errors in ("strict", "replace", "ignore", "backslashreplace")
        assert not type(stream) == type(self), "Cannot nest StreamEncoders"
        self.errors = errors
        self.bytecount = 0
        self.stream = stream
        
        if os.name == "nt":
            self.codec_name = "cp437"
        else:
            self.codec_name = locale.getpreferredencoding()

    def write(self, s):
        if type(s) != unicode:
            self.stream.write(s)
            return
        encoded_s = s.encode(self.codec_name, self.errors)
        self.stream.write(encoded_s)
        self.bytecount += len(encoded_s)

    def close(self):
        self.stream.close()

    def flush(self):
        self.stream.flush()

    def __enter__(self):
        """ Support for the 'with' statement """
        return self

    def __exit__(self, type, value, traceback):
        """ Support for the 'with' statement """
        self.close()

def dir_exists(path):
    return os.path.exists(path) and os.path.isdir(path)

def posix_normpath(path):
    """This function works similar to os.path.normpath(). The
    difference is that the behaviour of this function is guaranteed to
    be the same as os.path.normpath() on Linux, no matter what
    platform it is currently executing on. The argument must be
    unicode and must not contain backslash."""
    assert not "\\" in path, "expected posix style paths, was: %s" % path
    assert isinstance(path, unicode), "argument must be unicode"
    result = tounicode(os.path.normpath(path).replace("\\", "/"))
    assert not "\\" in result
    assert isinstance(result, unicode)
    return result


def unc_abspath(s):
    """This method works as os.abspath() except on Windows. On windows, it
    converts the path to an UNC path without using the broken python 2.x os.path
    tools."""
    if os.name != "nt":
        return os.path.abspath(s)
    if s.startswith(r"\\"):
        assert not "/" in s
        return s
    assert not s.startswith("\\")
    s = s.replace("/", "\\")
    if len(s) > 2 and s[1] == ":":
        # Likely a windows non-UNC absolute path
        return "\\\\?\\" + s
    return "\\\\?\\" + os.getcwd() + "\\" + s

def unc_makedirs(s):
    """This method works as os.makedirs() except on Windows. On windows, it
    first converts the path to an UNC path, thereby avoiding some limits on path
    length."""
    if os.name != "nt":
        return os.makedirs(s)
    unc_path = unc_abspath(s)
    unc_mount, unc_tail = os.path.splitunc(unc_path)
    unc_tail = unc_tail.lstrip("\\")
    dirnames = unc_tail.split("\\")
    path_to_mkdir = unc_mount
    for part in dirnames:
        path_to_mkdir += "\\" + part
        if not os.path.exists(path_to_mkdir):
            os.mkdir(path_to_mkdir)

def FakeFile():
    """ Behaves like a file object, but does not actually do anything."""
    return open(os.path.devnull, "w")

class RateLimiter:
    """This class makes it easy to perform some action only when a
    certain time has passed. The maxrate parameter is given in Hz and
    may be a float. The first call to ready() will always return
    True, and then the timer starts ticking."""

    def __init__(self, hz):
        self.min_period = 1.0 / hz
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

class ConstraintViolation(Exception):
    """This exception is thrown by a StrictFileWriter when there is a
    violation of a usage contract."""
    pass

class SizeViolation(ConstraintViolation):
    """This exception is thrown by a StrictFileWriter when the written
    file has more or less content than expected."""
    pass

class ContentViolation(ConstraintViolation):
    """This exception is thrown by a StrictFileWriter when the written
    file has a different content than expected."""
    pass


class StrictFileWriter:
    """This class will work as a file object when created, but with
    the additional functionality that it will not allow the file to
    exceed the given size. Also, the file must not exist before, and
    it must have the given md5 checksum when finished. If any of the
    contraints are violated, an ConstraintViolation exception is
    thrown.

    A sparse file with the given size will be created, which will
    reduce fragmentation on some platforms (NTFS). """
    def __init__(self, filename, md5, size, overwrite = False):
        assert is_md5sum(md5)
        assert type(size) == int or type(size) == long
        assert size >= 0
        self.filename = filename
        self.expected_md5 = md5
        self.expected_size = size
        if not overwrite and os.path.exists(filename):
            raise ConstraintViolation("Violation of file contract (file already exists): "+str(filename))
        self.f = open(self.filename, "wb")
        self.f.seek(0)
        self.f.truncate() # Erase any existing file content
        self.f.seek(size)
        self.f.truncate() # Create a sparse file to reduce file fragmentation on NTFS
        self.f.seek(0)
        self.md5summer = hashlib.md5()
        self.written_bytes = 0

    def write(self, buf):
        if self.written_bytes + len(buf) > self.expected_size:
            self.__close()
            raise SizeViolation("Violation of file contract (too big) detected: "+str(self.filename))
        self.md5summer.update(buf)
        if self.written_bytes + len(buf) == self.expected_size:
            if self.md5summer.hexdigest() != self.expected_md5:
                self.__close()
                raise ContentViolation("Violation of file contract (checksum) detected: "+str(self.filename))
        self.f.write(buf)
        self.written_bytes += len(buf)
    
    def close(self):
        if self.is_closed():
            return
        self.__close()
        if self.written_bytes != self.expected_size:
            raise SizeViolation("Violation of file contract (too small, %s < %s) detected: %s" %
                                   (self.written_bytes, self.expected_size, self.filename))

    def __close(self):
        """Closes the file without doing any constraint checks."""
        if not self.f:
            return
        self.f.close()
        self.f = None

    def is_closed(self):
        return self.f == None
        
    def __enter__(self):
        return self
    
    def __exit__(self, type, value, traceback):
        self.close()

 
