from common import *


def create_blob_reader(recipe, repo):
    assert recipe
    return RecipeReader(recipe, repo)

class RecipeReader:
    def __init__(self, recipe, repo):
        self.repo = repo
        self.pieces = recipe['pieces']
        self.size = recipe['size']
        # Where it is safe to read without switching source (virtual position)
        self.blob_source_range_start = 0
        self.source = None
        self.source_offset = 0
        self.source_size = 0
        self.pos = 0
        self.seek(0)

    def seek(self, pos):
        offset = 0
        if pos > self.size:
            raise Exception("Illegal position %s" % (pos))
        if pos == self.size:
            self.pos = pos
            self.source = None
            return
        for p in self.pieces:
            self.source = p["source"]
            self.blob_source_range_start = offset
            self.source_offset = p["offset"]
            self.source_size = p["size"]
            if offset + p["size"] > pos:
                self.pos = pos
                break
            offset += self.source_size
        assert self.pos == pos
        assert self.source
        assert is_md5sum(self.source)

    def __readable_bytes_without_seek(self):
        pos_from_source_start = self.pos - self.blob_source_range_start
        readable = self.source_size - pos_from_source_start
        return readable

    def read(self, readsize, pos = None):
        if pos != None:
            self.seek(pos)
        readsize = min(readsize, self.size - self.pos)
        result = ""
        while len(result) < readsize:
            blobpath = self.repo.get_blob_path(self.source)
            bytes_left = readsize - len(result)
            bytes_to_read = min(self.__readable_bytes_without_seek(), bytes_left)
            with open(blobpath, "rb") as f:
                f.seek(self.pos - self.blob_source_range_start)
                bytes = f.read(bytes_to_read)
            assert len(bytes) == bytes_to_read
            result += bytes
            self.seek(self.pos + len(bytes))
        assert readsize == len(result)
        return result
