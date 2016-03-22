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
        self.added_files = newfilenames.difference(basefilenames)
        identical_pairs = basepairs.intersection(newpairs)
        self.unchanged_files = set(dict(identical_pairs).keys())
        self.modified_files = newfilenames.difference(self.added_files, self.unchanged_files)

        # renamed_files is a set or list of (old_filename, new_filename, hash) whose
        # construction is to be implemented later.
        # These 3-tuples will reduce the added_files and deleted_files lists accordingly.
        # In order to keep the API and its results unchanged below so that the calling
        # code never notices any difference, in the methods below the added and deleted
        # files lists are augmented on the fly accordingly.
        self.renamed_files = []

    def __get_rename_deleted(self):
        """ Returns the filenames in the basetree that have been "deleted by rename". """
        return {renamed[0] for renamed in self.renamed_files}

    def __get_rename_added(self):
        """ Returns the filenames in the newtree that have been "added by rename". """
        return {renamed[1] for renamed in self.renamed_files}

    def as_tuple(self):
        # This would later be reverted/changed again to have an extra return value, that is:
        # return ...[as before], tuple(self.renamed_files)
        return tuple(self.unchanged_files), tuple(self.added_files.union(self.__get_rename_added())), \
            tuple(self.modified_files), tuple(self.deleted_files.union(self.__get_rename_deleted()))

    def all_filenames(self):
        return set(self.basetree.keys()).union(set(self.newtree.keys()))

    def all_changed_filenames(self):
        all_changed = self.added_files.union(self.__get_rename_added(),
            self.modified_files, self.deleted_files, self.__get_rename_deleted())
        assert(all_changed == self.all_filenames().difference(self.unchanged_files))   # Performance impact?
        return all_changed

    def is_deleted(self, filename):
        return filename in self.deleted_files or filename in self.__get_rename_deleted()

    def is_modified(self, filename):
        return filename in self.modified_files

    def is_new(self, filename):
        return filename in self.added_files or filename in self.__get_rename_added()

    def is_unchanged(self, filename):
        return filename in self.unchanged_files


def __selftest():
    oldlist = {"deleted.txt": "deleted content",
               "modified.txt": "modified content1",
               "unchanged.txt": "unchanged content",
               }

    newlist = {"modified.txt": "modified content2",
               "unchanged.txt": "unchanged content",
               "added.txt": "new content"
               }

    comp = TreeComparer(oldlist, newlist)
    assert comp.deleted_files == set(["deleted.txt"]), comp.deleted_files
    assert comp.unchanged_files == set(["unchanged.txt"]), comp.unchanged_files
    assert comp.added_files == set(["added.txt"]), comp.added_files
    assert comp.modified_files == set(["modified.txt"]), comp.modified_files

    assert comp.all_filenames() == set(["deleted.txt", "modified.txt", "unchanged.txt", "added.txt"])
    assert comp.all_changed_filenames() == set(["deleted.txt", "modified.txt", "added.txt"])

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

    assert not comp.is_modified("added.txt")
    assert not comp.is_deleted("added.txt")
    assert not comp.is_unchanged("added.txt")
    assert comp.is_new("added.txt")


__selftest()
