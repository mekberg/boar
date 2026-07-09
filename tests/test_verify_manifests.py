# -*- coding: utf-8 -*-

# Copyright 2026 Mats Ekberg
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

import sys, os, io, unittest
import importlib.util, importlib.machinery
from contextlib import redirect_stdout

BOAR_HOME = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BOAR_HOME)
sys.path.insert(0, os.path.join(BOAR_HOME, "macrotests"))

from common import md5sum


def load_boar_module():
    """Import the extensionless 'boar' CLI script as a module. Its platform
    setup and dispatch are guarded by __main__, so importing is side-effect
    free and lets us unit-test the command helpers directly."""
    loader = importlib.machinery.SourceFileLoader(
        "boarcli", os.path.join(BOAR_HOME, "boar"))
    spec = importlib.util.spec_from_loader("boarcli", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


boarcli = load_boar_module()


class StubBlob(object):
    def __init__(self, data):
        self._data = data

    def read(self):
        return self._data


class StubFront(object):
    """Minimal Front stand-in for verify_manifests: serves one snapshot's
    bloblist and the blobs it references."""

    def __init__(self, bloblist, blobs):
        self._bloblist = bloblist
        self._blobs = blobs  # md5 -> bytes

    def get_session_bloblist(self, sid):
        return self._bloblist

    def get_blob(self, md5):
        return StubBlob(self._blobs[md5])


def manifest_for(entries):
    """Build a classic md5sum-format manifest body from (md5, filename) pairs."""
    return "".join("%s  %s\n" % (md5, name) for md5, name in entries).encode("utf-8")


class TestVerifyManifests(unittest.TestCase):

    def testSummaryLineReportsFailingManifest(self):
        # Regression: on a file mismatch verify_manifests assigned a misspelled
        # "manifest_result", while the summary line printed "manifests_result"
        # (initialised to "OK" and never updated) -- so the per-manifest
        # summary always claimed "OK" even when a listed file failed. This
        # branch is only reachable on an already-corrupt snapshot (check-in
        # rejects inconsistent manifests), so it is exercised directly here.
        manifest_body = manifest_for([(md5sum(b"whatever"), "data.txt")])
        manifest_md5 = md5sum(manifest_body)
        # Snapshot contains the manifest but NOT the data.txt it lists.
        bloblist = [{"filename": "manifest-md5.txt", "md5sum": manifest_md5}]
        front = StubFront(bloblist, {manifest_md5: manifest_body})

        out = io.StringIO()
        with redirect_stdout(out):
            result = boarcli.verify_manifests(front, sid=1)
        output = out.getvalue()

        self.assertFalse(result)  # the mismatch is caught in the return value
        # ...and the human-readable summary line must say so too.
        self.assertIn("manifest-md5.txt ERROR", output)
        self.assertNotIn("manifest-md5.txt OK", output)

    def testValidManifestReportsOk(self):
        # A snapshot whose manifest matches its files verifies cleanly and the
        # summary line says OK -- guards against over-correcting the fix into
        # an always-ERROR summary.
        data = b"hello\n"
        data_md5 = md5sum(data)
        manifest_body = manifest_for([(data_md5, "data.txt")])
        manifest_md5 = md5sum(manifest_body)
        bloblist = [{"filename": "manifest-md5.txt", "md5sum": manifest_md5},
                    {"filename": "data.txt", "md5sum": data_md5}]
        front = StubFront(bloblist, {manifest_md5: manifest_body})

        out = io.StringIO()
        with redirect_stdout(out):
            result = boarcli.verify_manifests(front, sid=1)
        output = out.getvalue()

        self.assertTrue(result)
        self.assertIn("manifest-md5.txt OK", output)


if __name__ == '__main__':
    unittest.main()
