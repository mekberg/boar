#!/usr/bin/python
from __future__ import with_statement
import sys
import repository
import storage
import os
import stat
import sys

def print_help():
    print """Usage: 
ci <file>
co <file>
mkrepo <dir to create>
"""

def get_relative_path(p):
    """ Simply strips any leading slashes from the given path """
    # TODO: doesn't work on windows
    assert sys.platform.startswith("linux")
    while p.startswith("/"):
        p = p[1:]
    return p

def check_in_tree(repowriter, session_name, path):
    if path != get_relative_path(path):
        print "Warning: stripping leading slashes from given path"
    def visitor(arg, dirname, names):
        for name in names:
            full_path = os.path.join(dirname, name)
            if os.path.isdir(full_path):
                # print "Skipping directory:", full_path
                continue
            elif not os.path.isfile(full_path):
                print "Skipping non-file:", full_path
                continue

            print "Adding", full_path
            with open(full_path, "r") as f:
                data = f.read()
            st = os.lstat(full_path)
            blobinfo = {}
            blobinfo["filename"] = get_relative_path(full_path)
            blobinfo["ctime"] = st[stat.ST_CTIME]
            blobinfo["mtime"] = st[stat.ST_MTIME]
            repowriter.add(data, blobinfo)
    os.path.walk(path, visitor, None)


def cmd_ci(args):
    repopath = os.getenv("REPO_PATH")
    if repopath == None:
        print "You need to set REPO_PATH"
        return
    repo = repository.Repo(repopath)
    path_to_ci = args[0]
    assert os.path.exists(path_to_ci)
    s = storage.RepoWriter(repo)
    s.new_session()
    check_in_tree(s, "TestSession", path_to_ci)
    session_id = s.close_session()
    print "Checked in session id", session_id

def cmd_mkrepo(args):
    repository.create_repository(args[0])

def cmd_verify(args):
    repopath = os.getenv("REPO_PATH")
    if repopath == None:
        print "You need to set REPO_PATH"
        return
    repo = repository.Repo(repopath)
    repo.verify_all()

def main():
    if len(sys.argv) <= 1:
        print_help()
    elif sys.argv[1] == "ci":
        cmd_ci(sys.argv[2:])
    elif sys.argv[1] == "mkrepo":
        cmd_mkrepo(sys.argv[2:])
    elif sys.argv[1] == "verify":
        cmd_verify(sys.argv[2:])
    else:
        print_help()
        return

if __name__ == "__main__":
    main()
