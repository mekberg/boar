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
        """
        Possible cases:

            basetree                 newtree
            ===================      ===================
            deleted.txt    del   --
            modified.txt   mod1  --  modified.txt   mod2
            unchanged.txt  unch  --  unchanged.txt  unch
                                 --  added.txt      add
            old_name.txt   renm  --
                                 --  new_name.txt   renm

        Note that both sides can have additional files with hash "renm",
        not shown in the table above, in any combination of file names.
        """
        def invert_dict(tree):
            """ Turns {filename: hash} into {hash: [filenames]} """
            by_hash = {}
            for fn, h in tree.iteritems():
                if h in by_hash:
                    by_hash[h].append(fn)
                else:
                    by_hash[h] = [fn]
            return by_hash

        # Sets of filenames except for renamed_files, which keeps (old_name, new_name) tuples.
        self.deleted_files = set()
        self.modified_files = set()
        self.unchanged_files = set()
        self.added_files = set()
        self.renamed_files = set()

        newtree_by_hash = invert_dict(self.newtree)
        newtree_covered = set()     # We need this info, but don't want to mutate newtree.

        # This loop covers all possible cases except files that are truly new
        # in newtree (moves/renames are covered).
        for base_fn, base_hash in self.basetree.iteritems():
            if base_fn in self.newtree:
                if base_hash == self.newtree[base_fn]:
                    self.unchanged_files.add(base_fn)
                else:
                    self.modified_files.add(base_fn)
                newtree_covered.add(base_fn)
            else:
                if base_hash in newtree_by_hash:
                    for new_fn in newtree_by_hash[base_hash]:
                        # new_fn must be a truly new file, i.e. have no counterpart
                        # in basetree, and not been used as a rename target before.
                        if new_fn not in basetree and new_fn not in newtree_covered:
                            self.renamed_files.add((base_fn, new_fn))
                            newtree_covered.add(new_fn)
                            break
                    else:
                        # No suitable rename target found above, base_fn is truly deleted.
                        self.deleted_files.add(base_fn)
                else:
                    self.deleted_files.add(base_fn)

        # Any files in newtree not covered above must be truly new files
        # with no counterparts in basetree at all.
        for new_fn, new_hash in self.newtree.iteritems():
            if new_fn not in newtree_covered:
                self.added_files.add(new_fn)

        # Alternatively implementing the second loop immediately above
        # symmetrically to the first loop is almost possible, but is made very
        # difficult because it also had to reconstruct the rename pairs
        # *exactly* as the first loop. ==> it is much better and easier as done above.
        # for new_fn, new_hash in self.newtree.iteritems():
        #     if new_fn not in self.basetree:
        #         if new_hash in basetree_by_hash:
        #             for base_fn in basetree_by_hash[new_hash]:
        #                 # ...
        #                 if base_fn not in newtree and base_fn not in xxxx:
        #                     # ...
        #                     pass
        #         else:
        #             self.added_files.add(new_fn)

        assert(len(self.modified_files) + len(self.unchanged_files) +
            len(self.renamed_files) + len(self.deleted_files) == len(self.basetree))
        assert(len(self.modified_files) + len(self.unchanged_files) +
            len(self.renamed_files) + len(self.added_files) == len(self.newtree))

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
