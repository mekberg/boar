import os, sys, tempfile

from common import convert_win_path_to_unix, md5sum

boar_dirs = [".boar", ".boar_session"]
TMPDIR=tempfile.gettempdir()

def read_tree(path, skiplist = []):
    """Returns a mapping {filename: content, ...} for the given directory
    tree"""
    assert os.path.exists(path)
    def visitor(out_map, dirname, names):
        encoding = sys.getfilesystemencoding()
        dirname = dirname.decode(encoding)
        for skip in skiplist:
            if skip in names:
                names.remove(skip)
        for name in names:
            name = name.decode(encoding)
            fullpath = os.path.join(dirname, name)
            assert fullpath.startswith(path+os.path.sep), fullpath
            relpath = convert_win_path_to_unix(fullpath[len(path)+1:])
            if not os.path.isdir(fullpath):
                out_map[relpath] = open(fullpath).read()
    result = {}
    os.path.walk(path, visitor, result)
    return result

def write_tree(path, filemap, create_root = True):
    """Accepts a mapping {filename: content, ...} and writes it to the
    tree starting at the given """
    if create_root:
        os.mkdir(path)
    else:
        assert os.path.exists(path)
    for filename in filemap.keys():
        assert not os.path.exists(filename)
        assert not os.path.isabs(filename)
        fullpath = os.path.join(path, filename)
        dirpath = os.path.dirname(fullpath)
        try:
            os.makedirs(dirpath)
        except:
            pass
        with open(fullpath, "wb") as f:
            f.write(filemap[filename])

def write_file(directory, path, content):
    assert not os.path.isabs(path)
    filepath = os.path.join(directory, path)
    md5 = md5sum(content)
    with open(filepath, "w") as f:
        f.write(content)
    return md5

class WorkdirHelper:
    def mkdir(self, path):
        assert not os.path.isabs(path)
        dirpath = os.path.join(self.workdir, path)
        os.makedirs(dirpath)

    def addWorkdirFile(self, path, content):
        assert not os.path.isabs(path)
        filepath = os.path.join(self.workdir, path)
        md5 = md5sum(content)
        with open(filepath, "w") as f:
            f.write(content)
        return md5
    
    def rmWorkdirFile(self, path):
        assert not os.path.isabs(path)
        filepath = os.path.join(self.workdir, path)
        os.unlink(filepath)

    def createTmpName(self, suffix = ""):
        filename = tempfile.mktemp(prefix='testworkdir'+suffix+"_", dir=TMPDIR)
        filename = filename.decode()
        self.remove_at_teardown.append(filename)
        return filename

    def assertContents(self, path, expected_contents):
        with open(path, "rb") as f:
            file_contents = f.read()
            self.assertEquals(file_contents, expected_contents)

    
