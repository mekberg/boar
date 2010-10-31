#!/usr/bin/python
from __future__ import with_statement
import sys
import os
from time import time
import cProfile
from optparse import OptionParser
from blobrepo import repository
from blobrepo.sessions import bloblist_fingerprint
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

def cmd_locate(front, args):
    assert len(args) == 1, "Session name must be given"
    sessionName = args[0]
    repo_path = os.getenv("REPO_PATH")
    root = os.getcwd()
    tree = get_tree(root)
    tree.sort()
    wd = workdir.Workdir(front.get_repo_path(), sessionName, "", None, root)
    common_paths = None
    for f in tree:
        csum = md5sum_file(f)
        session_filenames = list(wd.get_filesnames(csum))
        session_dirs = [os.path.dirname(fn) for fn in session_filenames]
        if common_paths == None:
            common_paths = set(session_dirs)
        common_paths = common_paths.intersection(session_dirs)
        if not session_filenames:
            print "Missing:", f
            continue
        if session_filenames:
            print "OK:", f
            for p in session_filenames:
                print "   " + p
    if common_paths:
        print "All files occured in these dirs:", common_paths
    else:
        print "No session dir contained all files"

def cmd_status(args):
    verbose = ("-v" in args)
    wd = workdir.init_workdir(os.getcwd())
    assert wd, "No workdir found here"
    unchanged_files, new_files, modified_files, deleted_files, ignored_files \
        = wd.get_changes()
    filestats = {}
    def in_session(f):
        f_wd = strip_path_offset(wd.offset, f)
        return "S" if wd.exists_in_session(wd.cached_md5sum(f_wd)) else " "
    def in_workdir(f):
        csum = wd.get_blobinfo(f)['md5sum']
        return "W" if wd.exists_in_workdir(csum) else " "

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

def cmd_verify(front, args):
    print "Collecting a list of all sessions..."
    session_ids = front.get_session_ids()
    print "Verifying %s sessions" % (len(session_ids))
    ok_blobs = set()
    for i in range(0, len(session_ids)):
        id = session_ids[i]
        bloblist = front.get_session_bloblist(id)
        calc_fingerpring = bloblist_fingerprint(bloblist)
        assert calc_fingerpring == front.get_session_property(id, "fingerprint"), \
            "Fingerprint didn't match for session "+str(id)
        for bi in bloblist:
            assert bi['md5sum'] in ok_blobs or \
                front.has_blob(bi['md5sum']), "Session %s is missing blob %s" \
                % (session_ids[i], bi['md5sum'])
            ok_blobs.add(bi['md5sum'])
        print "Snapshot %s: All %s blobs ok" % (id, len(bloblist))
    print "Collecting a list of all blobs..."
    count = front.init_verify_blobs()
    print "Verifying %s blobs..." % (count)
    done = 0
    while done < count:
        done += len(front.verify_some_blobs())
        print done, "of "+str(count)+" blobs verified, "+ \
            str(round(1.0*done/count * 100,1)) + "% done."

def cmd_import(front, args):
    parser = OptionParser(usage="usage: %prog [options] <folder to import> <snapshot name>[/imported name]")
    parser.add_option("-n", "--dry-run", dest = "dry_run", action="store_true",
                      help="Don't actually do anything. Just show what will happen.")
    parser.add_option("-w", "--create-workdir", dest = "create_workdir", action="store_true",
                      help="Turn the imported directory into a workdir.")
    parser.add_option("--new-session", dest = "new_session", action="store_true",
                      help="Create a new session")
    base_session = None
    (options, args) = parser.parse_args(args)
    assert len(args) <= 2
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
    if options.new_session:
        assert not front.find_last_revision(session_name), \
            "There already exists a session named '"+session_name+"'"
    else:
        assert front.find_last_revision(session_name), "No session with the name '"+session_name+\
            "' exists. Add --new-session to create a new session."
    wd = workdir.Workdir(front.get_repo_path(), session_name, session_offset, None, path_to_ci)
    session_id = wd.checkin(write_meta = options.create_workdir, 
                            add_only = True, dry_run = options.dry_run)
    print "Checked in session id", session_id

def cmd_update(wd, args):
    wd.update()

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
    elif sys.argv[1] == "verify":
        front = init_repo_from_env()
        cmd_verify(front, sys.argv[2:])
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
    elif sys.argv[1] == "update":
        wd = workdir.init_workdir(os.getcwd())
        cmd_update(wd, sys.argv[2:])
    elif sys.argv[1] == "find":
        front = init_repo_from_env()
        cmd_find(front, sys.argv[2:])
    elif sys.argv[1] == "locate":
        front = init_repo_from_env()
        cmd_locate(front, sys.argv[2:])
    elif sys.argv[1] == "exportmd5":
        wd = workdir.init_workdir(os.getcwd())
        cmd_export_md5(wd, sys.argv[2:])
    else:
        print_help()
        return

if __name__ == "__main__":
    t1 = time()
    #cProfile.run('main()', "prof.txt")
    #import pstats
    #p = pstats.Stats('prof.txt')
    #p.sort_stats('cum').print_stats(10)
    main()
    t2 = time()
    print "Finished in", round(t2-t1, 2), "seconds"
