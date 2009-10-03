#!/usr/bin/python
from __future__ import with_statement
import sys
import repository
import os
import stat
import sys
import datetime
import time

from front import Front

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

def check_in_tree(sessionwriter, path):
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
            blobinfo["size"] = st[stat.ST_SIZE]
            sessionwriter.add(data, blobinfo)
    os.path.walk(path, visitor, None)

def list_sessions(front):
    sessions_count = {}
    for sid in front.get_session_ids():
        session_info = front.get_session_info(sid)
        name = session_info.get("name", "<no name>")
        sessions_count[name] = sessions_count.get(name, 0) + 1
    for name in sessions_count:
        print name, "(" + str(sessions_count[name]) + " revs)"

def list_revisions(front, session_name):
    for sid in front.get_session_ids():
        session_info = front.get_session_info(sid)
        bloblist = front.get_session_bloblist(sid)
        name = session_info.get("name", "<no name>")
        if name != session_name:
            continue
        print "Revision id", str(sid), "(" + session_info['date'] + "),", \
            len(bloblist), "files"

def list_files(front, session_name, revision):
    session_info = front.get_session_info(revision)
    name = session_info.get("name", "<no name>")
    if name != session_name:
        print "There is no such session/revision"
        return
    for info in front.get_session_bloblist(revision):
        print info['filename'], str(info['size']/1024+1) + "k"

def cmd_mkrepo(args):
    repository.create_repository(args[0])


def cmd_list(front, args):
    if len(args) == 0:
        list_sessions(front)
    elif len(args) == 1:
        list_revisions(front, args[0])
    elif len(args) == 2:
        list_files(front, args[0], args[1])
    else:
        print "Duuuh?"

def cmd_ci(front, args):
    path_to_ci = args[0]
    session_name = "MyTestSession"
    assert os.path.exists(path_to_ci)
    front.create_session()
    check_in_tree(front, path_to_ci)
    session_info = {}
    session_info["name"] = session_name
    session_info["timestamp"] = int(time.time())
    session_info["date"] = time.ctime()
    session_id = front.commit(session_info)
    print "Checked in session id", session_id

def cmd_co(front, args): 
    session_ids = front.get_session_ids()
    session_ids.reverse()
    session_name = args[0]
    for sid in session_ids:
        session_info = front.get_session_info(sid)
        name = session_info.get("name", "<no name>")
        if name == session_name:
            break
    if name != session_name:
        print "No such session found"
        return
    for info in front.get_session_bloblist(sid):
        print info['filename']
        data = front.get_blob(info['md5sum'])
        assert data
        if not os.path.exists(os.path.dirname(info['filename'])):
            os.makedirs(os.path.dirname(info['filename']))
        with open(info['filename'], "w") as f:            
            f.write(data)

def main():    
    repopath = os.getenv("REPO_PATH")
    if repopath == None:
        print "You need to set REPO_PATH"
        front = None
    else:
        front = Front(repository.Repo(repopath))

    if len(sys.argv) <= 1:
        print_help()
    elif sys.argv[1] == "mkrepo":
        cmd_mkrepo(sys.argv[2:])
    elif sys.argv[1] == "ci":
        cmd_ci(front, sys.argv[2:])
    elif sys.argv[1] == "list":
        cmd_list(front, sys.argv[2:])
    elif sys.argv[1] == "co":
        cmd_co(front, sys.argv[2:])
    else:
        print_help()
        return

if __name__ == "__main__":
    main()
