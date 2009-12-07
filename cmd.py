#!/usr/bin/python
from __future__ import with_statement
import sys
import repository
import os
import stat
import sys
import time
import client
import base64
import simplejson as json

from common import *

from front import Front
from common import *

def print_help():
    print """Usage: 
ci <file>
co <file>
mkrepo <dir to create>
"""

def find_last_revision(front, session_name):
    all_sids = front.get_session_ids()
    all_sids.sort()
    all_sids.reverse()
    for sid in all_sids:
        session_info = front.get_session_info(sid)
        name = session_info.get("name", "<no name>")
        if name == session_name:
            return sid
    return None

def get_blob(front, sum):
    """ Hack to wrap base64 encoding to make json happy """ 
    b64data = front.get_blob_b64(sum)
    data = base64.b64decode(b64data)
    return data

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
            file_sum = md5sum_file(full_path)
            st = os.lstat(full_path)
            blobinfo = {}
            blobinfo["filename"] = remove_first_dirname(full_path)
            blobinfo["ctime"] = st[stat.ST_CTIME]
            blobinfo["mtime"] = st[stat.ST_MTIME]
            blobinfo["size"] = st[stat.ST_SIZE]
            if sessionwriter.has_blob(file_sum):
                sessionwriter.add_existing(blobinfo, file_sum)
            else:
                with open(full_path, "rb") as f:
                    data = f.read()
                assert len(data) == blobinfo["size"]
                assert md5sum(data) == file_sum
                sessionwriter.add(base64.b64encode(data), blobinfo, file_sum)

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

def cmd_status(front, args):
    session_name, local_dir = args
    rev = find_last_revision(front, session_name)
    if rev == None:
        print "There is no session with the name '" + session_name + "'"
        return

    def visitor(out_list, dirname, names):
        for name in names:
            out_list.append(os.path.join(dirname, name))
    existing_files_list = []
    os.path.walk(local_dir, visitor, existing_files_list)
    print existing_files_list
    bloblist = front.get_session_bloblist(rev)
    unchanged_files = 0
    for info in bloblist:
        fname = os.path.join(local_dir, info['filename'])
        if fname in existing_files_list:
            existing_files_list.remove(fname)
        sum = info['md5sum']
        if not os.path.exists(fname):
            print "!", fname
        elif md5sum_file(fname) != sum:
            print "M", fname
        else:
            unchanged_files += 1
    print "There was", unchanged_files, "unchanged files"
    for fname in existing_files_list:
        print "?", fname

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
    session_name = args[1]

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

    if len(args) <= 1:
        workdir_path = session_name
    else:
        workdir_path = args[1]
    print "Exporting to workdir", "./" + workdir_path

    for sid in session_ids:
        session_info = front.get_session_info(sid)
        name = session_info.get("name", "<no name>")
        if name == session_name:
            break
    if name != session_name:
        print "No such session found"
        return

    # Write status file here
# Some random code
#     status_dir = ""
#     if not os.path.exists(dir):
#         os.mkdir(dir)
#     bloblist_filename = os.path.join(self.session_path, "bloblist.json")
#     assert not os.path.exists(bloblist_filename)
#     with open(bloblist_filename, "wb") as f:
#         json.dump(self.metadatas, f, indent = 4)
    # EOF

    assert not os.path.exists(workdir_path)
    for info in front.get_session_bloblist(sid):
        print info['filename']
        data = get_blob(front, info['md5sum'])
        assert data
        filename = os.path.join(workdir_path, info['filename'])
        if not os.path.exists(os.path.dirname(filename)):
            os.makedirs(os.path.dirname(filename))
        with open(filename, "wb") as f:            
            f.write(data)

def main():    
    if len(sys.argv) <= 1:
        print_help()
        return
    elif sys.argv[1] == "mkrepo":
        cmd_mkrepo(sys.argv[2:])
        return

    repopath = os.getenv("REPO_PATH")
    repourl = os.getenv("REPO_URL")
    front = None
    if repopath == None and repourl == None:
        print "You need to set REPO_PATH or REPO_URL"
    elif repopath and repourl:
        print "Both REPO_PATH and REPO_URL was set. Only one allowed"
    elif repopath:
        print "Using repo at '%s'" % (repopath)
        front = Front(repository.Repo(repopath))
    elif repourl:
        print "Using remote repo at '%s'" % (repourl)
        front = client.connect(repourl)

    if sys.argv[1] == "ci":
        cmd_ci(front, sys.argv[2:])
    elif sys.argv[1] == "list":
        cmd_list(front, sys.argv[2:])
    elif sys.argv[1] == "co":
        cmd_co(front, sys.argv[2:])
    elif sys.argv[1] == "status":
        cmd_status(front, sys.argv[2:])
    else:
        print_help()
        return

if __name__ == "__main__":
    t1 = time.time()
    main()
    t2 = time.time()
    print "Finished in", round(t2-t1, 2), "seconds"
