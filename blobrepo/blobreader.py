
def create_blob_reader(recipe):
    assert recipe

class RecipeReader:
    def __init__(self, recipe):
        self.pieces = recipe['pieces']
        # Where it is safe to read without switching source (virtual position)
        self.valid_start = 0
        self.source = None
        self.source_offset = 0
        self.source_size = 0
        self.pos = 0

    def seek(self, pos):
        offset = 0
        for p in self.pieces:
            if offset + p["size"] > pos:
                self.pos = pos
                return
            self.source = p["source"]
            self.valid_start = offset
            self.source_offset = p["offset"]
            self.source_size = p["size"]
            offset += self.source_size
        raise Exception("Illegal position %s" % (pos))

    def read(self, pos, size):
        self.seek(pos)
