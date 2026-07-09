# -*- coding: utf-8 -*-

# Copyright 2012 Mats Ekberg
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

import sys, os, unittest, tempfile, shutil, json
import subprocess

if __name__ == '__main__':
    boar_home = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, boar_home)
    sys.path.insert(0, os.path.join(boar_home, "macrotests"))

# import randtree
from common import get_tree, md5sum, md5sum_file, str2bytes, bytes2str

def call(cmd, check=True, cwd=None):
    """Execute a command and return output and status code. If 'check' is True,
    an exception will be raised if the command exists with an error code. If
    'cwd' is set, the command will execute in that directory."""
    assert isinstance(cmd, list)
    assert all(isinstance(x, str) for x in cmd)
    assert cwd is None or isinstance(cwd, str)
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, cwd=cwd)
    stdout = p.communicate()[0]
    returncode = p.poll()
    if check and returncode != 0:
        raise Exception("Call failed with errorcode %s: %s" % (returncode, stdout))
    return stdout, returncode

BOAR_HOME = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if __name__ == '__main__':
    sys.path.insert(0, BOAR_HOME)

if os.name == "nt":
    BOAR = os.path.join(BOAR_HOME, "boar.bat")
else:
    BOAR = os.path.join(BOAR_HOME, "boar")

def write_file(path, contents):
    with open(path, "wb") as f:
        f.write(str2bytes(contents))

class TestCli(unittest.TestCase):
    def setUp(self):
        self.testdir = tempfile.mkdtemp(prefix = self.__class__.__name__ + "_")
        os.chdir(self.testdir)
        self.setupRepo(u"TESTREPOåäö")
        self.setupSession(u"TestSessionåäö")

    def setupRepo(self, name):
        assert os.path.sep not in name
        call([BOAR, "mkrepo", name])
        assert os.path.exists(name)
        global REPO
        REPO = name

    def setupWorkdir(self, session, wdname = None, offset = ""):
        if wdname == None:
            wdname = session
        if offset:
            call([BOAR, "--repo", REPO, "co", session + "/" + offset, wdname])
        else:
            call([BOAR, "--repo", REPO, "co", session, wdname])
        global WORKDIR
        WORKDIR = wdname

    def setupSession(self, name):
        call([BOAR, "--repo", REPO, "mksession", name])
        global SESSION
        SESSION = name

    def tearDown(self):
        global REPO, SESSION, WORKDIR
        os.chdir(BOAR_HOME)
        shutil.rmtree(self.testdir)
        if "REPO" in globals(): del REPO,
        if "SESSION" in globals(): del SESSION
        if "WORKDIR" in globals(): del WORKDIR

    def testCat(self):
        testdata = b"a\n\b\n\c"
        call([BOAR, "--repo", REPO, "co", SESSION])
        write_file(os.path.join(SESSION, "fil.txt"), testdata)
        call([BOAR, "ci"], cwd=SESSION)
        output, returncode = call([BOAR, "--repo", REPO, "cat", os.path.join(SESSION, "fil.txt")])
        self.assertEqual(output, testdata)

    def testLogWorkdir(self):
        testdata = "Tjosan\nHejsan\n"
        call([BOAR, "--repo", REPO, "co", SESSION])
        os.mkdir(os.path.join(SESSION, "a"))
        write_file(os.path.join(SESSION, "a/fil.txt"), testdata)
        call([BOAR, "ci"], cwd=os.path.join(SESSION, "a"))
        output, returncode = call([BOAR, "log", "fil.txt"], cwd=os.path.join(SESSION, "a"))
        assert b"r2 | " in output
        assert returncode == 0

    def testPartialCommit(self):
        self.setupWorkdir(SESSION)
        file_new = "file_new.txt"
        file_modified = "file_modified.txt"
        file_deleted = "file_deleted.txt"
        file_notincluded = "file_notincluded.txt"
        file_unchanged = "file_unchanged.txt"

        # Prepare initial conditions
        write_file(os.path.join(WORKDIR, file_modified), "original contents")
        write_file(os.path.join(WORKDIR, file_unchanged), "unchanged contents")
        write_file(os.path.join(WORKDIR, file_deleted), "deleted contents")
        call([BOAR, "ci"], cwd=WORKDIR)

        # Set up the workdir for the partial commit
        write_file(os.path.join(WORKDIR, file_modified), "modified")
        os.unlink(os.path.join(WORKDIR, file_deleted))
        write_file(os.path.join(WORKDIR, file_new), "new")
        write_file(os.path.join(WORKDIR, file_notincluded), "not included")

        output, returncode = call([BOAR, "ci", file_new, file_modified, file_deleted], cwd=WORKDIR)
        assert b"Checked in session id 3" in output
        output, returncode = call([BOAR,  "--repo", REPO,
                                   "contents", "-r", "3", SESSION])
        parsed_output = sorted(json.loads(output)['files'], key=lambda x: x['filename'])
        for o in parsed_output:
            del o['mtime']
        self.assertEqual(parsed_output,
                         sorted([{"filename": "file_unchanged.txt",
                                "size": 18,
                                "md5": "eeefefca582568aabfbca7f5fce6a20a"
                                },
                               {"filename": "file_modified.txt",
                                "size": 8,
                                "md5": "9ae73c65f418e6f79ceb4f0e4a4b98d5"
                                },
                               {"filename": "file_new.txt",
                                "size": 3,
                                "md5": "22af645d1859cb5ca6da0c484f1f37ea"
                                }], key=lambda x: x['filename']))

    def testPartialCommitInOffsetWorkdir(self):
        self.setupWorkdir(SESSION, offset="subdir1")
        file_new = "file_new.txt"
        file_modified = "file_modified.txt"
        file_deleted = "file_deleted.txt"
        file_notincluded = "file_notincluded.txt"
        file_unchanged = "file_unchanged.txt"

        subdir2 = os.path.join(WORKDIR, "subdir2")
        os.mkdir(subdir2)

        # Prepare initial conditions
        write_file(os.path.join(subdir2, file_modified), "original contents")
        write_file(os.path.join(subdir2, file_unchanged), "unchanged contents")
        write_file(os.path.join(subdir2, file_deleted), "deleted contents")
        call([BOAR, "ci"], cwd=WORKDIR)

        # Set up the workdir for the partial commit
        write_file(os.path.join(subdir2, file_modified), "modified")
        os.unlink(os.path.join(subdir2, file_deleted))
        write_file(os.path.join(subdir2, file_new), "new")
        write_file(os.path.join(subdir2, file_notincluded), "not included")

        output, returncode = call([BOAR, "ci",
                                   os.path.join("subdir2", file_new),
                                   os.path.join("subdir2", file_modified),
                                   os.path.join("subdir2", file_deleted)], cwd=WORKDIR)
        assert b"Checked in session id 3" in output
        output, returncode = call([BOAR,  "--repo", REPO,
                                   "contents", "-r", "3", SESSION])
        parsed_output = sorted(json.loads(output)['files'], key=lambda x: x['filename'])
        for o in parsed_output:
            del o['mtime']
        self.assertEqual(parsed_output,
                              sorted([{"filename": "subdir1/subdir2/file_unchanged.txt",
                                "size": 18,
                                "md5": "eeefefca582568aabfbca7f5fce6a20a"
                                },
                               {"filename": "subdir1/subdir2/file_modified.txt",
                                "size": 8,
                                "md5": "9ae73c65f418e6f79ceb4f0e4a4b98d5"
                                },
                               {"filename": "subdir1/subdir2/file_new.txt",
                                "size": 3,
                                "md5": "22af645d1859cb5ca6da0c484f1f37ea"
                                }], key=lambda x: x['filename']))

    def testDiffrepoDetectsDivergentContent(self):
        # Regression test: two independent repos with the SAME number of
        # snapshots but DIFFERENT content must be reported as different.
        # front.is_identical() used to compare a repo to itself, which
        # degraded the identity test to equal session-id sets (sequential
        # revision numbers), so diffrepo wrongly called any two same-shaped
        # repos "identical" and clone/--replicate could skip needed work.
        def build_repo(reponame, contents):
            call([BOAR, "mkrepo", reponame])
            call([BOAR, "--repo", reponame, "mksession", "S"])
            wd = reponame + "_wd"
            call([BOAR, "--repo", reponame, "co", "S", wd])
            write_file(os.path.join(wd, "file.txt"), contents)
            call([BOAR, "ci"], cwd=wd)
            shutil.rmtree(wd)

        build_repo("repoA", "content A")
        build_repo("repoB", "content B")  # same shape, different content

        output, returncode = call([BOAR, "diffrepo", "repoA", "repoB"],
                                  check=False)
        self.assertIn(b"Repositories differ", output)
        self.assertEqual(returncode, 1)

        # A true clone must still be reported identical (guard against
        # over-correcting is_identical into always-different).
        call([BOAR, "clone", "repoA", "repoA_clone"])
        output, returncode = call([BOAR, "diffrepo", "repoA", "repoA_clone"],
                                  check=False)
        self.assertIn(b"Repositories are identical", output)
        self.assertEqual(returncode, 0)

    def testManifestsRequireFlagAcceptsPresentManifest(self):
        # Regression: verify_manifests did `del <set>[key]`, which raises
        # TypeError the instant a --require'd manifest is actually present
        # -- i.e. exactly the success case the -e flag exists to confirm.
        self.setupWorkdir(SESSION)
        data = b"hello manifest\n"
        write_file(os.path.join(WORKDIR, "data.txt"), data)
        # A self-describing manifest: its filename embeds the md5 of its
        # own content, and its body is a valid md5sum listing of data.txt.
        manifest_body = ("%s  data.txt\n" % md5sum(data)).encode("utf-8")
        manifest_md5 = md5sum(manifest_body)
        write_file(os.path.join(WORKDIR, "manifest-%s.md5" % manifest_md5),
                   manifest_body)
        call([BOAR, "ci"], cwd=WORKDIR)

        output, returncode = call(
            [BOAR, "--repo", REPO, "manifests", "-e", manifest_md5, SESSION],
            check=False)
        self.assertEqual(returncode, 0, output)


if __name__ == '__main__':
    unittest.main()

