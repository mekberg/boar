from common import *
from jsonrpc import DataSource
import deduplication
import compression
import boar_exceptions
from copy import copy

# Size of the chunks used when streaming compressed data to/from a
# decompressor. Just a reasonable value, not part of any format.
DECOMP_CHUNK_SIZE = 2 ** 16

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

A "compress" recipe has the same shape but an additional "algorithm"
field. Its pieces, concatenated, form the compressed data; decompressing
that data with the named algorithm yields the original blob. "size" is
the size of the decompressed (original) data.
"""

def create_recipe_reader(recipe, repo, offset = 0, size = None, local_path = None):
    """Return a streaming reader for the given recipe, dispatching on its
    'method'. This is the entry point that understands every recipe type."""
    assert recipe
    method = recipe.get('method')
    if method == "concat":
        return RecipeReader(recipe, repo, offset = offset, size = size, local_path = local_path)
    if method == "compress":
        return CompressReader(recipe, repo, offset = offset, size = size, local_path = local_path)
    raise boar_exceptions.CorruptionError("Unknown recipe method: %r" % (method,))

def create_blob_reader(recipe, repo):
    assert recipe
    return create_recipe_reader(recipe, repo)

class RecipeReader(DataSource):
    def __init__(self, recipe, repo, offset = 0, size = None, local_path = None):
        assert offset >= 0
        assert size == None or size >= 0
        assert recipe['method'] == "concat"
        assert 'md5sum' in recipe and is_md5sum(recipe['md5sum'])
        assert 'size' in recipe and recipe['size'] >= 0
        self.repo = repo
        self.local_path = local_path
        self.progress_callback = lambda x: None

        self.pieces = []
        self.blob_paths = {} # Blob id -> blob path
        self.file_handles = {} # blob -> handle

        # Expand repeated pieces
        piece_size_sum = 0
        for piece in recipe['pieces']:
            repeat = piece.get('repeat', 1)
            for n in range(0, repeat):
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

    @overrides(DataSource)
    def bytes_left(self):
        return self.bytes_left_in_segment

    def __del__(self):
        for f in list(self.file_handles.values()):
            f.close()
        del self.file_handles

    def __read_from_blob(self, blob, position, size):
        blobpath = self.blob_paths[blob]
        if blobpath not in self.file_handles:
            for f in list(self.file_handles.values()):
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

    @overrides(DataSource)
    def read(self, readsize = None):
        assert self.bytes_left_in_segment >= 0
        if readsize == None:
            readsize = self.bytes_left_in_segment
        readsize = min(self.bytes_left_in_segment, readsize)
        assert readsize >= 0

        result = b""
        while len(result) < readsize:
            #print self.segment_start_in_recipe, self.segment_size, self.bytes_left_in_segment
            current_recipe_read_position = self.segment_start_in_recipe + (self.segment_size - self.bytes_left_in_segment)
            self.current_piece_index = self.__search_forward(current_recipe_read_position, start_index = self.current_piece_index)
            remaining = readsize - len(result)
            data = self.__read_piece_data(self.pieces[self.current_piece_index], current_recipe_read_position, remaining)
            if not data:
                # The source blob is shorter than the recipe claims (a
                # truncated/corrupt blob on disk). Without this guard the
                # loop would spin forever making no progress.
                raise boar_exceptions.CorruptionError(
                    "Blob %s is truncated: a recipe expected more data than is present on disk"
                    % self.pieces[self.current_piece_index]['source'])
            result += data
            self.bytes_left_in_segment -= len(data)
        self.progress_callback(calculate_progress(self.segment_size, self.segment_size - self.bytes_left_in_segment))
        return result

    def set_progress_callback(self, progress_callback):
        assert callable(progress_callback)
        self.progress_callback = progress_callback


class CompressReader(DataSource):
    """Streaming reader for a "compress" recipe. It reads the compressed
    data by concatenating the recipe's pieces (reusing RecipeReader) and
    decompresses it on the fly with the algorithm named in the recipe,
    so the original blob never has to be materialised in full."""

    def __init__(self, recipe, repo, offset = 0, size = None, local_path = None):
        assert recipe['method'] == "compress"
        assert 'md5sum' in recipe and is_md5sum(recipe['md5sum'])
        assert 'algorithm' in recipe
        assert 'size' in recipe and recipe['size'] >= 0
        assert offset >= 0
        assert size == None or size >= 0
        self.md5sum = recipe['md5sum']
        self.total_size = recipe['size']
        if size == None:
            size = self.total_size - offset
        assert offset + size <= self.total_size
        self.segment_size = size
        self.bytes_left_in_segment = size
        self.progress_callback = lambda x: None

        self.decompressor = compression.get_codec(recipe['algorithm']).decompressor()

        # The compressed data is itself just a concatenation of raw
        # blobs, so reuse a RecipeReader to stream it.
        pieces = recipe['pieces']
        compressed_size = sum(piece['size'] * piece.get('repeat', 1) for piece in pieces)
        compressed_recipe = {"method": "concat",
                             "md5sum": "0" * 32, # not verified, just needs to be well-formed
                             "size": compressed_size,
                             "pieces": pieces}
        self.compressed = RecipeReader(compressed_recipe, repo, offset = 0,
                                       size = compressed_size, local_path = local_path)

        self.buffer = bytearray()
        self.buffer_pos = 0
        if offset:
            self.__skip(offset)

    @overrides(DataSource)
    def bytes_left(self):
        return self.bytes_left_in_segment

    def __pump(self):
        """Decompress a little more into the buffer. Returns False only
        when no further progress is possible (end of stream, or the
        compressed input is exhausted while more is still required).

        Note: some decompressors (notably lz4's frame decompressor) report
        needs_input == False right after a length-limited read, but then
        return zero bytes on the following drain call before flipping
        needs_input back to True. A zero-byte step is therefore not treated
        as a stall as long as the codec still has, or has just asked for,
        input."""
        if self.decompressor.eof:
            return False
        if self.decompressor.needs_input:
            if self.compressed.bytes_left() == 0:
                return False
            feed = self.compressed.read(min(self.compressed.bytes_left(), DECOMP_CHUNK_SIZE))
        else:
            feed = b""
        produced = self.decompressor.decompress(feed, DECOMP_CHUNK_SIZE)
        if produced:
            self.buffer += produced
            return True
        # No output this step. If we supplied no input and the codec still
        # does not want any, the stream is genuinely stuck.
        if not feed and not self.decompressor.needs_input:
            return False
        return True

    def __emit(self, count):
        """Produce and consume up to `count` decompressed bytes."""
        while (len(self.buffer) - self.buffer_pos) < count:
            if not self.__pump():
                break
        out = bytes(self.buffer[self.buffer_pos : self.buffer_pos + count])
        self.buffer_pos += len(out)
        if self.buffer_pos > 2 ** 20:
            del self.buffer[:self.buffer_pos]
            self.buffer_pos = 0
        return out

    def __skip(self, n):
        while n > 0:
            got = self.__emit(min(n, DECOMP_CHUNK_SIZE))
            if not got:
                raise boar_exceptions.CorruptionError(
                    "Compressed blob %s is truncated or corrupt" % self.md5sum)
            n -= len(got)

    @overrides(DataSource)
    def read(self, readsize = None):
        if readsize == None:
            readsize = self.bytes_left_in_segment
        readsize = min(readsize, self.bytes_left_in_segment)
        assert readsize >= 0
        out = self.__emit(readsize)
        if len(out) < readsize:
            raise boar_exceptions.CorruptionError(
                "Compressed blob %s is truncated or corrupt" % self.md5sum)
        self.bytes_left_in_segment -= len(out)
        self.progress_callback(calculate_progress(self.segment_size,
                                                  self.segment_size - self.bytes_left_in_segment))
        return out

    def set_progress_callback(self, progress_callback):
        assert callable(progress_callback)
        self.progress_callback = progress_callback


def benchmark():
    import tempfile
    blob_fo = tempfile.NamedTemporaryFile()
    blob_path = blob_fo.name
    class FakeRepo(object):
        def get_blob_path(self, blob):
            return blob_path
    block_size = 65536
    block_count = 10000
    blob_fo.write(b"\0" * block_size)
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
    print((block_size * block_count) / float(2**20), "Mbytes")
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
    class FakeRepo(object):
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
    print(reader.read())


if __name__ == "__main__":
    benchmark()
    #simple_test()
