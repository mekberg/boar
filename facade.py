import repository

repopath = os.getenv("REPO_PATH")
repo = repository.Repo(repopath)

def get_all_sessions(self):
    session_dirs = []
    for dir in os.listdir(os.path.join(self.repopath, SESSIONS_DIR)):
        if re.match("^[0-9]+$", dir) != None:
            session_dirs.append(int(dir))
    session_dirs.sort()
    return session_dirs

def get_session(self, id):
    return sessions.SessionReader(self, id)

def create_session(self):
    return sessions.SessionWriter(self)

def add(self, data, metadata = {}, original_sum = None):
    assert self.session_path != None
    sum = md5sum(data)
    if original_sum:
        assert sum == md5sum, "Calculated checksum did not match client provided checksum"
    metadata["md5sum"] = sum
    fname = os.path.join(self.session_path, sum)
    existing_blob_path = self.repo.get_blob_path(sum)
    existing_blob = os.path.exists(existing_blob_path)
    if not existing_blob and not os.path.exists(fname):
        with open(fname, "w") as f:
            f.write(data)
    self.metadatas.append(metadata)
    return sum

def commit(self, sessioninfo = {}):
    assert self.session_path != None

    bloblist_filename = os.path.join(self.session_path, "bloblist.json")
    assert not os.path.exists(bloblist_filename)
    with open(bloblist_filename, "w") as f:
        json.dump(self.metadatas, f, indent = 4)

    session_filename = os.path.join(self.session_path, "session.json")
    assert not os.path.exists(session_filename)
    with open(session_filename, "w") as f:
        json.dump(sessioninfo, f, indent = 4)

    queue_dir = self.repo.get_queue_path("queued_session")
    assert not os.path.exists(queue_dir)

    print "Committing to", queue_dir, "from", self.session_path, "..."
    shutil.move(self.session_path, queue_dir)
    print "Done committing."
    print "Consolidating changes..."
    id = self.repo.process_queue()
    print "Consolidating changes complete"
    return id

def verify(self):
    for blobinfo in self.bloblist:
        sum = blobinfo['md5sum']
        if checked_blobs.has_key(sum):
            is_ok = checked_blobs[sum]
        else:
            is_ok = self.repo.verify_blob(blobinfo['md5sum'])
            checked_blobs[sum] = is_ok
        print blobinfo['filename'], is_ok

def get_all_files(self):
    for blobinfo in self.bloblist:
        info = copy.copy(blobinfo)
        with open(self.repo.get_blob_path(info['md5sum']), "r") as f:
            info['data'] = f.read()
        assert md5sum(info['data']) == info['md5sum']
        yield info
