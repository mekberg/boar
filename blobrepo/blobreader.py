from common import *
from jsonrpc import DataSource
import deduplication

""" A recipe has the following format:

{
    "method": "concat",
    "md5sum": "9b97d0a697dc503fb4c53ea01bd23dc7",
    "size": 8469,

    "pieces": [
       {"source": "82a6c69d071b6d84b18912a2fa6725a4",
        "offset": 0,
        "size": 5000},
       {"source": "c7eac275a3810a395fda6eeb7786c0e9",
        "offset": 0,
        "size": 3469}
    ]
}

"""

def create_blob_reader(recipe, repo):
    assert recipe
    return RecipeReader(recipe, repo)

class RecipeReader(DataSource):
    def __init__(self, recipe, repo, offset = 0, size = None, local_path = None):
        assert offset >= 0
        assert size == None or size >= 0
        self.repo = repo
        self.local_path = local_path

        self.pieces = []
        self.blob_paths = {} # Blob id -> blob path

        # Expand repeated pieces
        for piece in recipe['pieces']:
            repeat = piece.get('repeat', 1)
            for n in xrange(0, repeat):
                self.pieces.append(piece)

            blob = piece['source']
            blobpath = None
            if self.local_path:
                blobpath =  os.path.join(self.local_path, blob)
            if not blobpath or not os.path.exists(blobpath):
                blobpath = self.repo.get_blob_path(blob)
            assert os.path.exists(blobpath)
            self.blob_paths[piece['source']] = blobpath

        self.blob_size = recipe['size']
        if size == None:
            size = recipe['size']
        assert offset + size <= recipe['size']
        self._bytes_left = size        

        # Where it is safe to read without switching source (virtual position)
        self.blob_source_range_start = 0
        self.source = None
        self.source_offset = 0
        self.source_size = 0
        self.pos = offset
        self.__seek(self.pos)
        #print "Reader opening recipe:"
        #deduplication.print_recipe(recipe)
        self.file_handles = {} # blob -> handle

    def remaining(self): # TODO: make less silly
        return self.bytes_left(self)

    def bytes_left(self):
        return self._bytes_left

    def __seek(self, seek_pos):
        offset = 0
        if seek_pos > self.blob_size:
            raise Exception("Illegal position %s" % (seek_pos))
        if seek_pos == self.blob_size:
            self.pos = seek_pos
            self.source = None
            return
        for p in self.pieces:
            # Ignore repeat here - already taken care of at init
            self.source = p["source"]
            self.blob_source_range_start = offset
            self.source_offset = p["offset"]
            self.source_size = p["size"]
            if offset + p["size"] > seek_pos:
                self.pos = seek_pos
                break
            offset += self.source_size
        assert self.pos == seek_pos
        assert self.source
        assert is_md5sum(self.source)


    def __readable_bytes_without_seek(self):
        pos_from_source_start = self.pos - self.blob_source_range_start
        readable = self.source_size - pos_from_source_start
        return readable

    def __get_handle(self, path):
        if path not in self.file_handles:
            self.file_handles[path] = open(path, "rb")
        return self.file_handles[path]

    def __del__(self):
        for f in self.file_handles.values():
            f.close()
        del self.file_handles

    def read(self, readsize = None):
        if readsize == None:
            readsize = self.bytes_left()
        assert readsize >= 0
        assert self._bytes_left >= 0
        readsize = min(self._bytes_left, readsize)
        result = ""
        while len(result) < readsize:
            bytes_left = readsize - len(result)
            bytes_to_read = min(self.__readable_bytes_without_seek(), bytes_left)

            #print self.pos, self.blob_source_range_start, self.source_offset
            blobpath = self.blob_paths[self.source]
            source_file_pos = self.pos - self.blob_source_range_start + self.source_offset
            source_file_size = os.path.getsize(blobpath)
            assert source_file_pos <= source_file_size, "Source file %s is of unexpected size (seek to %s, is only %s)" % (blobpath, source_file_pos, source_file_size)
            f = self.__get_handle(blobpath)
            f.seek(source_file_pos)
            bytes = f.read(bytes_to_read)
            #print "Reader is reading from %s %s+%s" % (self.source, source_file_pos, bytes_to_read)

            assert len(bytes) == bytes_to_read
            result += bytes
            self.__seek(self.pos + len(bytes))
        assert readsize == len(result), "%s != %s" % (readsize, len(result))
        self._bytes_left -= readsize
        assert self._bytes_left >= 0
        return result
