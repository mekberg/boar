#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2013 Mats Ekberg
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

"""
This module contains some tools that can be helpful when writing a
program that needs to access a boar repository.

This module takes care not to import any boar code. It only uses the
boar cli tool API. This makes this module useful even for verifying
the behaviour of boar itself.
"""

import json
import re
import sys
import hashlib
import subprocess
import os
import re

boar_cmd = "boar"
if os.name == 'nt':
    boar_cmd = "boar.bat"

class RunCommandException(Exception):
    pass

class IntegrityError(Exception):
    pass

def is_md5sum(s):
    try:
        return re.match("^[a-f0-9]{32}$", s) != None
    except TypeError:
        return False

def run_command(*cmdlist):
    """Execute a shell command and return the output. Raises an
    exception if the command failed for any reason."""
    return "".join(run_command_streamed(*cmdlist))

def run_command_streamed(*cmdlist):
    """Execute a shell command and return the output as a sequence of
    blocks. Raises an exception if the command failed for any
    reason."""
    process = subprocess.Popen(cmdlist,
                               stdout=subprocess.PIPE)
    while True:
        data = process.stdout.read(4096)
        if data == "":
            break
        yield data
    status = process.wait()
    if status != 0:
        raise RunCommandException("Command '%s' failed with error %s" %
                                  (cmdlist, status))

def load_blob(reader):
    """Given a reader object, such as returned by ExtBoar.get_blob(),
    fetches all the blocks and returns the reconstructed
    data. Warning: this means the whole blob will be loaded into
    RAM."""
    return "".join(reader)

class ExtRepo:
    def __init__(self, repourl):
        self.repourl = repourl

        try:
            run_command(boar_cmd, "--version")
        except OSError, e:
            if e.errno == 2:
                raise Exception("Couldn't execute boar. Did you forget to add it to your path?")
            raise

        try:
            # Dummy command just to see if we can access the repo
            run_command(boar_cmd, "--repo", repourl, "log", "-r0:0")
        except:
            raise Exception("Failed opening repository %s" % repourl)

    def get_blob_by_path(self, session_name, path):
        """This function will stream the given blob from the
        repository. It will yield the file as a sequence of blocks. It
        does NOT perform any explicit checksum verification.
        """
        reader = run_command_streamed(boar_cmd, "--repo", self.repourl, "cat", "--punycode",
                                      (session_name + "/" + path).encode("punycode"))
        return reader

    def get_blob(self, md5):
        """This function will stream the given blob from the
        repository. It will yield the file as a sequence of blocks. As a
        bonus, it will verify the integrity of the data.
        """
        assert is_md5sum(md5), "Not a valid md5sum: %s" % md5
        reader = run_command_streamed(boar_cmd, "--repo", self.repourl, "cat", "--blob", md5)
        summer = hashlib.md5()
        for block in reader:
            summer.update(block)
            yield block
        if summer.hexdigest() != md5:
            raise IntegrityError("Invalid checksum for blob: %s Got: %s" % (md5, summer.hexdigest()))

    def verify_blob(self, md5):
        # Trust get_blob() to verify the data for us
        try:
            for block in self.get_blob(md5):
                pass
        except RunCommandException:
            raise IntegrityError("Blob %s is missing: There was an error while reading the blob from the repository" % md5)

    def get_all_session_names(self):
        session_names = json.loads(run_command(boar_cmd, "--repo", self.repourl, "sessions", "--json"))
        return session_names

    def get_session_contents(self, session_name):
        session_contents = json.loads(run_command(boar_cmd, "--repo", self.repourl,
                                                  "contents", "--punycode", session_name.encode("punycode")))
        return session_contents


