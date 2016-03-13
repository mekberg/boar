# -*- encoding: utf-8 -*-

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

class TreeComparer:
    def __init__(self, basetree, newtree):
        """ A tree is defined by a dict on the form
        {filename: fingerprint} """
        assert type(basetree) == dict
        assert type(newtree) == dict
        self.basetree = basetree
        self.newtree = newtree
        self.__compare()

    def __compare(self):
        basefilenames = set(self.basetree.keys())
        newfilenames = set(self.newtree.keys())
        basepairs = set(self.basetree.items())
        newpairs = set(self.newtree.items())
        self.deleted_files = basefilenames.difference(newfilenames)
        self.new_files = newfilenames.difference(basefilenames)
        identical_pairs = basepairs.intersection(newpairs)
        self.unchanged_files = set(dict(identical_pairs).keys())
        self.modified_files = newfilenames.difference(self.new_files, self.unchanged_files)

    def as_tuple(self):
        return tuple(self.unchanged_files), tuple(self.new_files), tuple(self.modified_files), tuple(self.deleted_files)

    def all_filenames(self):
        return set(self.basetree.keys()).union(set(self.newtree.keys()))

    def all_changed_filenames(self):
        return self.new_files.union(self.modified_files).union(self.deleted_files)

    def is_deleted(self, filename):
        return filename in self.deleted_files

    def is_modified(self, filename):
        return filename in self.modified_files

    def is_new(self, filename):
        return filename in self.new_files

    def is_unchanged(self, filename):
        return filename in self.unchanged_files


def __selftest():
    oldlist = {"deleted.txt": "deleted content",
               "modified.txt": "modified content1",
               "unchanged.txt": "unchanged content",
               }

    newlist = {"modified.txt": "modified content2",
               "unchanged.txt": "unchanged content",
               "new.txt": "new content"
               }

    comp = TreeComparer(oldlist, newlist)
    assert comp.deleted_files == set(["deleted.txt"]), comp.deleted_files
    assert comp.unchanged_files == set(["unchanged.txt"]), comp.unchanged_files
    assert comp.new_files == set(["new.txt"]), comp.new_files
    assert comp.modified_files == set(["modified.txt"]), comp.modified_files

    assert comp.all_filenames() == set(["deleted.txt", "modified.txt", "unchanged.txt", "new.txt"])
    assert comp.all_changed_filenames() == set(["deleted.txt", "modified.txt", "new.txt"])

    assert comp.is_modified("modified.txt")
    assert not comp.is_deleted("modified.txt")
    assert not comp.is_unchanged("modified.txt")
    assert not comp.is_new("modified.txt")

    assert not comp.is_modified("deleted.txt")
    assert comp.is_deleted("deleted.txt")
    assert not comp.is_unchanged("deleted.txt")
    assert not comp.is_new("deleted.txt")

    assert not comp.is_modified("unchanged.txt")
    assert not comp.is_deleted("unchanged.txt")
    assert comp.is_unchanged("unchanged.txt")
    assert not comp.is_new("unchanged.txt")

    assert not comp.is_modified("new.txt")
    assert not comp.is_deleted("new.txt")
    assert not comp.is_unchanged("new.txt")
    assert comp.is_new("new.txt")


__selftest()
