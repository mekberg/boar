#!/usr/bin/python
from __future__ import with_statement
import sys
import os
from time import time
import cProfile

from blobrepo import repository
import client

if sys.version_info >= (2, 6):
    import json
else:
    import simplejson as json

from front import Front
import workdir
from common import *
import settings

def print_help():
    print """Usage: 
import [-w] [-u] <dir> <session_name>
co <session_name> [destination]
mkrepo <dir to create>
list [session_name [revision_id]]
find <filename>
"""

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
    verbose = ("-v" in args)
    wd = workdir.init_workdir(os.getcwd())
    unchanged_files, new_files, modified_files, deleted_files, ignored_files \
        = wd.get_changes()
    #print unchanged_files, new_files, modified_files, deleted_files, ignored_files
    filestats = {}
    def in_session(f):
        return "C" if wd.exists_in_session(wd.cached_md5sum(f)) else " "
    def in_workdir(f):
        csum = wd.get_blobinfo(f)['md5sum']
        return "C" if wd.exists_in_workdir(csum) else " "

    for f in new_files:
        filestats[f] = "A" + in_session(f)
    for f in modified_files:
        filestats[f] = "M" + in_workdir(f)
    for f in deleted_files:
        filestats[f] = "D" + in_workdir(f)
    if verbose:
        for f in unchanged_files:
            filestats[f] = " "
        for f in ignored_files:
            filestats[f] = "i"
    filenames = filestats.keys()
    filenames.sort()
    for f in filenames:
        print filestats[f], f

def cmd_info(args):
    wd = workdir.init_workdir(os.getcwd())
    if wd:
        print "Using a work directory:"
        print "   Workdir root:", wd.root
        print "   Repository:", wd.repoUrl
        print "   Session:", wd.sessionName, "/", wd.offset
        print "   Revision:", wd.revision
        
    #env_front = init_repo_from_env()

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
    base_session = None
    update_import = True
    create_workdir = False
    dry_run = False
    if "-n" in args:
        args.remove("-n")
        dry_run = True
#    if "-r" in args:
#        args.remove("-r")
#        update_import = False
    if "-w" in args:
        args.remove("-w")
        create_workdir = True

    path_to_ci = os.path.abspath(args[0])
    session_name = os.path.basename(args[0])
    session_offset = ""
    if len(args) > 1:
        if "/" in args[1]:
            # TODO: this won't work so well with windows paths
            session_name, session_offset = args[1].split("/", 1)
        else:
            session_name = args[1]
    print "Session name:", session_name, "Session offset:", session_offset
    assert os.path.exists(path_to_ci), "Did not exist: " + path_to_ci
    wd = workdir.Workdir(front.get_repo_path(), session_name, session_offset, None, path_to_ci)
    session_id = wd.checkin(write_meta = create_workdir, add_only = update_import, dry_run = dry_run)
    print "Checked in session id", session_id


def cmd_ci(wd, args):
    session_id = wd.checkin()
    print "Checked in session id", session_id

def cmd_co(front, args): 
    session_ids = front.get_session_ids()
    session_ids.reverse()
    session_name, throwaway, offset = args[0].partition("/")

    if len(args) <= 1:
        workdir_path = os.path.abspath(session_name)
    else:
        workdir_path = os.path.abspath(args[1])
    print "Exporting to workdir", workdir_path

    for sid in session_ids:
        session_info = front.get_session_info(sid)
        name = session_info.get("name", "<no name>")
        if name == session_name:
            break
    if name != session_name:
        print "No session named '%s' found" % (session_name)
        return
    assert not os.path.exists(workdir_path)
    os.mkdir(workdir_path)
    wd = workdir.Workdir(front.get_repo_path(), session_name, offset, sid, workdir_path)
    wd.checkout()

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

def cmd_export_md5(wd, args):
    wd.export_md5()

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
        front = Front(repository.Repo(repopath))
    elif repourl:
        print "Using remote repo at '%s'" % (repourl)
        front = client.connect(repourl)
    if front == None:
        raise Exception(msg)
    return front


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
        cmd_info(sys.argv[2:])
    elif sys.argv[1] == "ci":
        wd = workdir.init_workdir(os.getcwd())
        cmd_ci(wd, sys.argv[2:])
    elif sys.argv[1] == "find":
        front = init_repo_from_env()
        cmd_find(front, sys.argv[2:])
    elif sys.argv[1] == "exportmd5":
        wd = workdir.init_workdir(os.getcwd())
        cmd_export_md5(wd, sys.argv[2:])
    else:
        print_help()
        return

if __name__ == "__main__":
    t1 = time()
    #cProfile.run('main()')
    main()
    t2 = time()
    print "Finished in", round(t2-t1, 2), "seconds"
