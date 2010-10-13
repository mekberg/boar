# -*- encoding: utf-8 -*-

class TreeComparer:
    def __init__(self, basetree, newtree):
        """ A tree is defined by a dict on the form
        {filename: fingerprint} """
        self.basetree = basetree
        self.newtree = newtree
        self.compare()

    def compare(self):
        basefilenames = set(self.basetree.keys())
        newfilenames = set(self.newtree.keys())
        basepairs = set(self.basetree.items())
        newpairs = set(self.newtree.items())
        self.deleted_files = tuple(basefilenames.difference(newfilenames))
        self.new_files = tuple(newfilenames.difference(basefilenames))
        identical_pairs = basepairs.intersection(newpairs)
        self.unchanged_files = tuple(dict(identical_pairs).keys())
        self.modified_files = tuple(newfilenames.difference(self.new_files, self.unchanged_files))

def selftest():

    oldlist = {"deleted.txt": "deleted content",
               "modified.txt": "modified content1",
               "unchanged.txt": "unchanged content",
               }

    newlist = {"modified.txt": "modified content2",
               "unchanged.txt": "unchanged content",
               "new.txt": "new content"
               }

    comp = TreeComparer(oldlist, newlist)
    assert comp.deleted_files == ("deleted.txt",), comp.deleted_files
    assert comp.unchanged_files == ("unchanged.txt",), comp.unchanged_files
    assert comp.new_files == ("new.txt",), comp.new_files
    assert comp.modified_files == ("modified.txt",), comp.modified_files

selftest()
