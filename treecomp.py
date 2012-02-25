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
        self.deleted_files = tuple(basefilenames.difference(newfilenames))
        self.new_files = tuple(newfilenames.difference(basefilenames))
        identical_pairs = basepairs.intersection(newpairs)
        self.unchanged_files = tuple(dict(identical_pairs).keys())
        self.modified_files = tuple(newfilenames.difference(self.new_files, self.unchanged_files))

    def as_tuple(self):
        return self.unchanged_files, self.new_files, self.modified_files, self.deleted_files        

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
    assert comp.deleted_files == ("deleted.txt",), comp.deleted_files
    assert comp.unchanged_files == ("unchanged.txt",), comp.unchanged_files
    assert comp.new_files == ("new.txt",), comp.new_files
    assert comp.modified_files == ("modified.txt",), comp.modified_files

__selftest()
