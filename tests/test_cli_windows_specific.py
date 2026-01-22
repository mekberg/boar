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

import sys, os, unittest, tempfile, shutil
import subprocess

if __name__ == '__main__':
    boar_home = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, boar_home)
    sys.path.insert(0, os.path.join(boar_home, "macrotests"))

# import randtree
from common import get_tree, md5sum, md5sum_file, str2bytes

def call(cmd, check=True, cwd=None):
    """Execute a command and return output and status code. If 'check' is True,
    an exception will be raised if the command exists with an error code. If
    'cwd' is set, the command will execute in that directory."""
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
        self.testdir = tempfile.mkdtemp(prefix="boar_test_cli_")
        os.chdir(self.testdir)
        call([BOAR, "mkrepo", "TESTREPOåäö"])
        assert os.path.exists("TESTREPOåäö")
        output, returncode = call([BOAR, "mkrepo", "TESTREPOåäö"], check=False)
        assert returncode == 1
        call([BOAR, "--repo", "TESTREPOåäö", "mksession", "TestSessionåäö"])
        assert b"ERROR: File or directory already exists" in output

    def tearDown(self):
        os.chdir(BOAR_HOME)
        shutil.rmtree(self.testdir)

    def testCat(self):
        # Use valid escapes: newline, backspace, newline, then 'c'
        testdata = b"a\n\b\nc"
        call([BOAR, "--repo", "TESTREPOåäö", "co", "TestSessionåäö"])
        write_file("TestSessionåäö/fil.txt", testdata)
        call([BOAR, "ci"], cwd="TestSessionåäö")
        output, returncode = call([BOAR, "--repo", "TESTREPOåäö", "cat", "TestSessionåäö/fil.txt"])
        self.assertEqual(output, testdata)

    def testLogWorkdir(self):
        testdata = "Tjosan\nHejsan\n"
        call([BOAR, "--repo", "TESTREPOåäö", "co", "TestSessionåäö"])
        os.mkdir("TestSessionåäö/a/")
        write_file("TestSessionåäö/a/fil.txt", testdata)
        call([BOAR, "ci"], cwd="TestSessionåäö/a")
        output, returncode = call([BOAR, "log", "fil.txt"], cwd="TestSessionåäö/a")
        assert b"r2 | " in output
        assert returncode == 0

class TestCliWindowsSpecific(unittest.TestCase):
    def setUp(self):
        self.testdir = tempfile.mkdtemp(prefix="boar_test_cli_windows_")
        os.chdir(self.testdir)

    def tearDown(self):
        os.chdir(BOAR_HOME)
        shutil.rmtree(self.testdir)

    #
    # Actual tests start here
    #
    def testNoArgs(self):
        output, returncode = call([BOAR], check=False)
        assert b"Usage: boar" in output
        assert returncode == 1

    def testMkrepo(self):
        assert not os.path.exists("TESTREPO")
        call([BOAR, "mkrepo", "TESTREPO"])
        assert os.path.exists("TESTREPO")

    def testEmpty(self):
        pass

    @unittest.skipUnless(os.name == "nt", "Windows-specific encoding test")
    def testLocateUnicodeFilenameToFile(self):
        """Test that locate command handles Unicode filenames correctly when 
        stdout is redirected to a file (uses cp1252 encoding on Windows).
        
        This tests for the bug:
        UnicodeEncodeError: 'charmap' codec can't encode character '\u0416' 
        in position 52: character maps to <undefined>
        
        The character '\u0416' is Cyrillic capital letter ZHE (Ж), which cannot
        be represented in Windows-1252 (cp1252) encoding.
        """
        # Create a repository and session
        call([BOAR, "mkrepo", "TESTREPO"])
        call([BOAR, "--repo", "TESTREPO", "mksession", "TestSession"])
        call([BOAR, "--repo", "TESTREPO", "co", "TestSession"])
        
        # Create a file with ASCII filename but commit it first
        # to establish a working session
        ascii_filename = "TestSession/test_file.txt"
        test_content = "test content for locate"
        write_file(ascii_filename, test_content)
        call([BOAR, "ci"], cwd="TestSession")
        
        # Create a local file with Cyrillic characters in the filename
        # '\u0416' is Cyrillic capital letter ZHE (Ж)
        # This character cannot be encoded in cp1252 (Windows-1252)
        local_cyrillic_file = "Локальный_Ж_файл.txt"  # Local file with Cyrillic name
        write_file(local_cyrillic_file, test_content)  # Same content as repo file
        
        # The bug occurs when stdout is redirected to a file
        # Python uses cp1252 encoding on Windows when redirecting to a file
        output_file = "locate_output.txt"
        
        # Use shell=True to simulate the user's command line experience with redirection
        # This is the scenario that triggers the bug: boar locate ... > file.txt
        cmd = '"%s" --repo TESTREPO locate TestSession "%s" > "%s" 2>&1' % (
            BOAR, local_cyrillic_file, output_file)
        
        # Run through cmd.exe to get proper redirection behavior
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            cwd=self.testdir
        )
        
        # Check if output file was created
        output_exists = os.path.exists(output_file)
        if output_exists:
            with open(output_file, "rb") as f:
                output_content = f.read()
        else:
            output_content = b""
        
        # The command should complete without a UnicodeEncodeError
        # If the bug exists, the output will contain "UnicodeEncodeError"
        self.assertNotIn(b"UnicodeEncodeError", output_content,
            "locate command failed with Unicode encoding error. Output: %s" % output_content)
        
        # Also check return code
        self.assertEqual(result.returncode, 0, 
            "locate command failed with Unicode filename. Output: %s" % output_content)


if __name__ == '__main__':
    unittest.main()

