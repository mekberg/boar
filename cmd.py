#!/usr/bin/python
from __future__ import with_statement
import sys
import os
import stat
import sys
import time
import base64

import repository
import bloblist
import client

if sys.version_info >= (2, 6):
    import json
else:
    import simplejson as json

from front import Front
from common import *

metadir = ".meta"

def print_help():
    print """Usage: 
ci <dir> <session_name>
co <session_name> [destination]
mkrepo <dir to create>
list [session_name [revision_id]]
"""

def get_blob(front, sum):
    """ Hack to wrap base64 encoding to make json happy """ 
    b64data = front.get_blob_b64(sum)
    data = base64.b64decode(b64data)
    return data

def check_in_tree(sessionwriter, path):
    if path != get_relative_path(path):
        print "Warning: stripping leading slashes from given path"

    def visitor(arg, dirname, names):
        if metadir in names:
            print "Ignoring meta directory", os.path.join(dirname, metadir)
            names.remove(metadir)
        for name in names:
            full_path = os.path.join(dirname, name)
            if os.path.isdir(full_path):
                # print "Skipping directory:", full_path
                continue
            elif not os.path.isfile(full_path):
                print "Skipping non-file:", full_path
                continue
            elif os.path.islink(full_path):
                print "Skipping symbolic link:", full_path
                continue                

            print "Adding", full_path
            blobinfo = bloblist.create_blobinfo(full_path, path)
            
            if sessionwriter.has_blob(blobinfo["md5sum"]):
                sessionwriter.add_existing(blobinfo, blobinfo["md5sum"])
            else:
                with open(full_path, "rb") as f:
                    data = f.read()
                assert len(data) == blobinfo["size"]
                assert md5sum(data) == blobinfo["md5sum"]
                sessionwriter.add(base64.b64encode(data), blobinfo, blobinfo["md5sum"])

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

def cmd_status(args):
    front = init_repo_from_meta(os.getcwd())
    assert front, "No workdir found here"
    metapath = find_meta(os.getcwd())
    info = load_meta_info(metapath)
    session_name = info['session_name']
    local_dir = os.path.split(metapath)[0]
    rev = front.find_last_revision(session_name)
    if rev == None:
        print "There is no session with the name '" + session_name + "'"
        return
    verbose = ( "-v" in args )
    def visitor(out_list, dirname, names):
        if metadir in names:
            names.remove(metadir)
        for name in names:
            out_list.append(os.path.join(dirname, name))

    existing_files_list = []
    os.path.walk(local_dir, visitor, existing_files_list)
    #print existing_files_list
    bloblist = front.get_session_bloblist(rev)
    blobs_by_csum = {}
    for b in bloblist:
        blobs_by_csum[b['md5sum']] = b
    unchanged_files = 0
    file_status = {} # Filename -> Statuscode
    for info in bloblist:
        fname = os.path.join(local_dir, info['filename'])
        if fname in existing_files_list:
            existing_files_list.remove(fname)
        sum = info['md5sum']
        if not os.path.exists(fname):
            file_status[fname] = "!"
        elif md5sum_file(fname) != sum:
            file_status[fname] = "M"
        else:
            file_status[fname] = " "
            unchanged_files += 1
            
    for fname in existing_files_list:
        file_status[fname] = "?"
    filenames = file_status.keys()
    filenames.sort()
    for f in filenames:
        if file_status[f] != " " or verbose:
            print file_status[f], f

def cmd_info(front, args):
    pass

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

def cmd_import(front, args):
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


def cmd_ci(workdir, args):
    path_to_ci = workdir.root
    front = workdir.get_front()
    session_name = workdir.sessionName
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

    assert not os.path.exists(workdir_path)
    os.mkdir(workdir_path)
    os.mkdir(os.path.join(workdir_path, metadir))
    statusfile = os.path.join(workdir_path, metadir, "info")
    with open(statusfile, "wb") as f:
        json.dump({'repo_path': front.get_repo_path(),
                   'session_name': session_name,
                   'session_id': sid}, f, indent = 4)    

    for info in front.get_session_bloblist(sid):
        print info['filename']
        data = get_blob(front, info['md5sum'])
        assert data or info['size'] == 0
        filename = os.path.join(workdir_path, info['filename'])
        if not os.path.exists(os.path.dirname(filename)):
            os.makedirs(os.path.dirname(filename))
        with open(filename, "wb") as f:            
            f.write(data)

def cmd_find(front, args):
    filename, = args
    cs = md5sum_file(filename)
    all_ids = front.get_session_ids()
    all_ids.sort()
    all_ids.reverse()
    seen = set()
    for i in all_ids:
        info = front.get_session_info(i)
        if info['name'] in seen:
            continue
        seen.add(info['name'])
        for bi in front.get_session_bloblist(i):
            if bi['md5sum'] == cs:
                print info['name'] +":"+bi['filename']


def init_repo_from_env():
    repopath = os.getenv("REPO_PATH")
    repourl = os.getenv("REPO_URL")
    front = None
    msg = None
    if not repopath and not repourl:
        msg = "You need to set REPO_PATH or REPO_URL"
    elif repopath and repourl:
        msg = "Both REPO_PATH and REPO_URL was set. Only one allowed"
    elif repopath:
        print "Using repo at '%s'" % (repopath)
        front = Front(repository.Repo(repopath))
    elif repourl:
        print "Using remote repo at '%s'" % (repourl)
        front = client.connect(repourl)
    if front == None:
        raise Exception(msg)
    return front

def find_meta(path):
    meta = os.path.join(path, metadir)
    if os.path.exists(meta):
        return meta
    head, tail = os.path.split(path)
    if head == path:
        return None
    return find_meta(head)

def load_meta_info(metapath):
    with open(os.path.join(metapath, "info"), "rb") as f:
        info = json.load(f)
    return info

def init_repo_from_meta(path):
    front = None
    msg = None
    meta = find_meta(path)
    if meta:
        print "Found meta data at", meta
    else:
        print "No metadata found"
        return None

    info = load_meta_info(meta)
    repo_path = info['repo_path']
    session_name = info['session_name']
    session_id = info['session_id']

    print "Using repo at", repo_path, "with session", session_name
    front = Front(repository.Repo(repo_path))
    return front

def init_workdir(path):
    front = init_repo_from_meta(path)
    assert front, "No workdir found here"
    metapath = find_meta(os.getcwd())
    info = load_meta_info(metapath)
    root = os.path.split(metapath)[0]    
    wd = Workdir(repoUrl=info['repo_path'], 
                 sessionName=info['session_name'], 
                 revision=info['session_id'],
                 root=root) 
    return wd

class Workdir:
    def __init__(self, repoUrl, sessionName, revision, root):
        self.repoUrl = repoUrl
        self.sessionName = sessionName
        self.revision = revision
        self.root = root
        self.front = None

    def get_front(self):
        if not self.front:
            self.front = Front(repository.Repo(self.repoUrl))
        return self.front

def main():    
    if len(sys.argv) <= 1:
        print_help()
        return
    elif sys.argv[1] == "mkrepo":
        cmd_mkrepo(sys.argv[2:])
        return

    if sys.argv[1] == "import":
        front = init_repo_from_env()
        cmd_import(front, sys.argv[2:])
    elif sys.argv[1] == "list":
        front = init_repo_from_env()
        cmd_list(front, sys.argv[2:])
    elif sys.argv[1] == "co":
        front = init_repo_from_env()
        cmd_co(front, sys.argv[2:])
    elif sys.argv[1] == "status":
        cmd_status(sys.argv[2:])
    elif sys.argv[1] == "info":
        front = init_repo_from_meta(os.getcwd())
        cmd_info(front, sys.argv[2:])
    elif sys.argv[1] == "ci":
        wd = init_workdir(os.getcwd())
        cmd_ci(wd, sys.argv[2:])
    elif sys.argv[1] == "find":
        front = init_repo_from_env()
        cmd_find(front, sys.argv[2:])
    else:
        print_help()
        return

if __name__ == "__main__":
    t1 = time.time()
    main()
    t2 = time.time()
    print "Finished in", round(t2-t1, 2), "seconds"
