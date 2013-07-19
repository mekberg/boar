from common import *
from jsonrpc import DataSource
import deduplication
import boar_exceptions
from copy import copy

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
        assert recipe['method'] == "concat"
        assert 'md5sum' in recipe and is_md5sum(recipe['md5sum'])
        assert 'size' in recipe and recipe['size'] >= 0
        self.repo = repo
        self.local_path = local_path

        self.pieces = []
        self.blob_paths = {} # Blob id -> blob path
        self.file_handles = {} # blob -> handle

        # Expand repeated pieces
        piece_size_sum = 0
        for piece in recipe['pieces']:
            repeat = piece.get('repeat', 1)
            for n in xrange(0, repeat):
                piece_to_add = copy(piece)
                piece_to_add['position_in_recipe'] = piece_size_sum
                piece_size_sum += piece['size']
                self.pieces.append(piece_to_add)
            blob = piece['source']
            blobpath = None
            if self.local_path:
                blobpath =  os.path.join(self.local_path, blob)
            if not blobpath or not os.path.exists(blobpath):
                blobpath = self.repo.get_blob_path(blob)
            if not os.path.exists(blobpath):
                raise boar_exceptions.CorruptionError("A recipe (%s) refers to a missing blob (%s)" % (recipe['md5sum'], blob))
            self.blob_paths[piece['source']] = blobpath

        if piece_size_sum != recipe['size']:
            raise boar_exceptions.CorruptionError("Recipe is internally inconsistent: %s" % recipe['md5sum'])

        self.recipe_size = recipe['size']
        if size == None:
            self.segment_size = recipe['size'] - offset
        else:
            self.segment_size = size

        self.bytes_left_in_segment = self.segment_size
        self.segment_start_in_recipe = offset
        self.current_piece_index = 0

        assert self.segment_start_in_recipe + self.bytes_left_in_segment <= recipe['size']


    def bytes_left(self):
        return self.bytes_left_in_segment

    def __del__(self):
        for f in self.file_handles.values():
            f.close()
        del self.file_handles

    def __read_from_blob(self, blob, position, size):
        blobpath = self.blob_paths[blob]
        if blobpath not in self.file_handles:
            for f in self.file_handles.values():
                f.close()
            self.file_handles.clear()
            self.file_handles[blobpath] = open(blobpath, "rb")
        f = self.file_handles[blobpath]
        f.seek(position)
        data = f.read(size)
        #print "read_from_blob(blob=%s, position=%s, size=%s) => '%s'" % (blob, position, size, data)
        return data

    def __search_forward(self, pos, start_index = 0):
        index = start_index
        while True:
            piece = self.pieces[index]
            piece_start = piece['position_in_recipe']
            piece_end = piece_start + piece['size']
            if piece_start <= pos < piece_end:
                break
            index += 1
        #print "search_forward(%s, %s) => %s" % (pos, start_index, index)
        return index

    def __read_piece_data(self, piece, recipe_pos, max_size):
        piece_pos = recipe_pos - piece['position_in_recipe']
        blob_pos = piece['offset'] + piece_pos
        available_blob_data_size = piece['size'] - piece_pos
        blob_read_size = min(available_blob_data_size, max_size)
        return self.__read_from_blob(piece['source'], blob_pos, blob_read_size)

    def read(self, readsize = None):
        assert self.bytes_left_in_segment >= 0
        if readsize == None:
            readsize = self.bytes_left_in_segment
        readsize = min(self.bytes_left_in_segment, readsize)
        assert readsize >= 0

        result = ""
        while len(result) < readsize:
            #print self.segment_start_in_recipe, self.segment_size, self.bytes_left_in_segment
            current_recipe_read_position = self.segment_start_in_recipe + (self.segment_size - self.bytes_left_in_segment)
            self.current_piece_index = self.__search_forward(current_recipe_read_position, start_index = self.current_piece_index)
            remaining = readsize - len(result)
            data = self.__read_piece_data(self.pieces[self.current_piece_index], current_recipe_read_position, remaining)
            result += data
            self.bytes_left_in_segment -= len(data)
        return result


def benchmark():
    import tempfile
    blob_fo = tempfile.NamedTemporaryFile()
    blob_path = blob_fo.name
    class FakeRepo:
        def get_blob_path(self, blob):
            return blob_path
    block_size = 65536
    block_count = 10000
    blob_fo.write("\0" * block_size)
    recipe = {"md5sum": "00000000000000000000000000000000",
              "method": "concat",
              "size": block_size * block_count,
              "pieces": [
            {"source": "00000000000000000000000000000000",
             "offset": 0,
             "size": block_size,
             "repeat": block_count
             } ]
              }
    reader = RecipeReader(recipe, FakeRepo())
    print block_size * block_count / (2**20), "Mbytes"
    sw = StopWatch()
    reader.read()
    sw.mark("Read complete")
    """
    62 Mbytes
    SW: Read complete 0.33 (total 0.33)
    125 Mbytes
    SW: Read complete 1.14 (total 1.14)
    250 Mbytes
    SW: Read complete 4.29 (total 4.29)
    625 Mbytes
    SW: Read complete 26.12 (total 26.12)
    """

def simple_test():
    import tempfile
    blob_path = "/tmp/blobreader-test.txt"
    class FakeRepo:
        def get_blob_path(self, blob):
            return blob_path
    with open(blob_path, "w") as f:
        f.write("abcdefghijklmnopqrstuvwxyz")
    recipe = {"md5sum": "00000000000000000000000000000000",
              "method": "concat",
              "size": 9,
              "pieces": [
            {"source": "00000000000000000000000000000000",
             "offset": 3,
             "size": 3,
             "repeat": 3
             } 
            ]
              }
    reader = RecipeReader(recipe, FakeRepo())
    print reader.read()


if __name__ == "__main__":
    benchmark()
    #simple_test()
