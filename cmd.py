#!/usr/bin/python
from __future__ import with_statement
import sys
import repository
import storage
import os

def print_help():
    print """Usage: 
ci <file>
co <file>
mkrepo <dir to create>
"""



def cmd_ci(args):
    repopath = os.getenv("REPO_PATH")
    if repopath == None:
        print "You need to set REPO_PATH"
        return
    repo = repository.Repo(repopath)
    path_to_ci = args[0]
    assert os.path.exists(path_to_ci)
    s = storage.RepoWriter(repo)
    s.new_session("TestSession")
    def visitor(arg, dirname, names):
        for name in names:
            print "Visiting", dirname, name
            full_path = os.path.join(dirname, name)
            if not os.path.isfile(full_path):
                continue
            with open(full_path, "r") as f:
                data = f.read()
            s.add(data, {"filename": full_path})
        
    os.path.walk(path_to_ci, visitor, None)

    s.close_session()


def cmd_mkrepo(args):
    repository.create_repository(args[0])

def main():
    if len(sys.argv) <= 1:
        print_help()
    elif sys.argv[1] == "ci":
        cmd_ci(sys.argv[2:])
    elif sys.argv[1] == "mkrepo":
        cmd_mkrepo(sys.argv[2:])
    else:
        print_help()
        return

if __name__ == "__main__":
    main()
