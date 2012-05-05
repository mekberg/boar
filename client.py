#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2010 Mats Ekberg
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

import jsonrpc
import base64
import re
import sys
import tempfile

import subprocess
from front import Front
from blobrepo import repository
from common import *
from boar_exceptions import *

BOAR_URL_PATTERN = "boar\+([a-z]+)://.*"

def is_boar_url(string):
    return re.match(BOAR_URL_PATTERN, string) != None

def localize(repourl):
    m = re.match(BOAR_URL_PATTERN, repourl)
    if not m:
        repourl="boar+local://" + os.path.abspath(repourl)
    return repourl

def connect(repourl):
    #repourl = localize(repourl)

    m = re.match(BOAR_URL_PATTERN, repourl)
    if not m:
        return Front(user_friendly_open_local_repository(repourl))

    transporter = m.group(1)
    if transporter == "ssh":
        front = connect_ssh(repourl)
    elif transporter == "nc":
        front = connect_nc(repourl)
    elif transporter == "local":
        front = connect_local(repourl)
    else:
        raise UserError("No such transporter: '%s'" % transporter)
    assert front
    return front    

def user_friendly_open_local_repository(path):
    # This won't catch invalid/nonexisting repos. Let the repo constructor do that
    path = os.path.abspath(path)
    if repository.looks_like_repo(path) and repository.has_pending_operations(path):
        notice("The repository at %s has pending operations. Resuming..." % os.path.basename(path))
        repo = repository.Repo(path)
        notice("Pending operations completed.")
    else:
        repo = repository.Repo(path)
    return repo

def _connect_cmd(cmd):
    errorlog = tempfile.TemporaryFile()
    #errorlog = open("/tmp/errors.txt", "w")
    p = subprocess.Popen(cmd, 
                         shell = True, 
                         stdout = subprocess.PIPE, 
                         stdin = subprocess.PIPE, 
                         stderr = errorlog)    
    if p.poll():
        errorlog.seek(0)
        errorstr = errorlog.read().strip()
        raise UserError("Transport command failed with error code %s: %s" % (p.returncode, errorstr))
    server = jsonrpc.ServerProxy(jsonrpc.JsonRpc20(), 
                                 jsonrpc.TransportStream(p.stdout, p.stdin))
    try:
        assert server.ping() == "pong"
    except:
        print "*** Transport command stderr output:"
        errorlog.seek(0)
        print errorlog.read()
        print "*** Local stack trace:"
        raise
    server.initialize()
    return server.front

def connect_ssh(url):
    url_match = re.match("boar\+ssh://(.*)@([^/]+)(/.*)", url)
    assert url_match, "Not a valid ssh Boar URL:" + url
    user, host, path = url_match.groups()
    cmd = "ssh '%s'@'%s' boarserve.py '%s'" % (user, host, path)
    return _connect_cmd(cmd)

def connect_nc(url):
    url_match = re.match("boar\+nc://(.*):(\d+)/?", url)
    assert url_match, "Not a valid netcat Boar URL:" + url
    host, port = url_match.groups()
    cmd = "nc %s %s" % (host, port)
    return _connect_cmd(cmd)

def connect_local(url):
    url_match = re.match("boar\+local://(.*)/?", url)
    assert url_match, "Not a valid local Boar URL:" + url
    repopath, = url_match.groups()
    boarhome = os.path.dirname(os.path.abspath(__file__))
    cmd = "'%s/boarserve.py' '%s'" % (boarhome, repopath)
    return _connect_cmd(cmd)

