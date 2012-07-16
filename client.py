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
import socket

import subprocess
from front import Front
from blobrepo import repository
from common import *
from boar_exceptions import *

BOAR_URL_PATTERN = "boar(\+(local|ssh|tcp))?://.+"

def is_boar_url(string):
    return re.match(BOAR_URL_PATTERN, string) != None

def localize(repourl):
    if not is_boar_url(repourl):
        repourl="boar+local://" + os.path.abspath(repourl)
    return repourl

def ssh_localize(repourl):
    if not is_boar_url(repourl):
        repourl="boar+ssh://localhost" + os.path.abspath(repourl)
    return repourl

def connect(repourl):
    if os.getenv("BOAR_TEST_REMOTE_REPO") == "1":
        # Force boar to use the remote communication mechanism even for local repos.
        repourl = localize(repourl)
    elif os.getenv("BOAR_TEST_REMOTE_REPO") == "2":
        # Force boar to use the remote communication mechanism over ssh 
        repourl = ssh_localize(repourl)

    m = re.match(BOAR_URL_PATTERN, repourl)
    if not m:
        return Front(user_friendly_open_local_repository(repourl))

    transporter = m.group(2)
    if transporter == None or transporter == "tcp":
        front = connect_tcp(repourl)
    elif transporter == "ssh":
        front = connect_ssh(repourl)
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

def create_boar_proxy(from_server, to_server):
    server = jsonrpc.ServerProxy(jsonrpc.BoarMessageClient(from_server, to_server))
    try:
        assert server.ping() == "pong"
    except ConnectionLost, e:
        raise UserError("Could not connect to remote repository: %s" % e)
    except:
        raise
    server.initialize()
    return server

def _connect_tcp(host, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((host, port))
    to_server = s.makefile(mode="wb")
    from_server = s.makefile(mode="rb")
    server = create_boar_proxy(to_server, from_server)
    return server.front

def _connect_cmd(cmd):
    p = subprocess.Popen(cmd, 
                         shell = True, 
                         stdout = subprocess.PIPE, 
                         stdin = subprocess.PIPE, 
                         stderr = None)    
    if p.poll():
        raise UserError("Transport command failed with error code %s" % (p.returncode))
    server = create_boar_proxy(p.stdout, p.stdin)
    return server.front

def connect_ssh(url):
    url_with_user_match = re.match("boar\+ssh://(.*)@([^/]+)(/.*)", url)
    url_without_user_match = re.match("boar\+ssh://([^@/]+)(/.*)", url)
    if url_with_user_match:
        user, host, path = url_with_user_match.groups()
    elif url_without_user_match:
        user = None
        host, path = url_without_user_match.groups()
    else:
        raise UserError("Not a valid boar ssh URL: "+str(url))
    ssh_cmd = __get_ssh_command()
    cmd = '%s "%s" boar serve -S "%s"' % (ssh_cmd, host, path)
    if user:
        cmd = '%s -l "%s" "%s" boar serve -S "%s"' % (ssh_cmd, user, host, path)
    return _connect_cmd(cmd)

def connect_tcp(url):
    url_match = re.match("boar(\+tcp)?://(.*):(\d+)/?", url)
    assert url_match, "Not a valid Boar URL:" + url
    _, host, port = url_match.groups()
    port = int(port)
    try:
        return _connect_tcp(host, port)
    except socket.error, e:
        raise UserError("Network error: %s" % e)

def connect_local(url):
    url_match = re.match("boar\+local://(.*)/?", url)
    assert url_match, "Not a valid local Boar URL:" + url
    repopath, = url_match.groups()
    boarhome = os.path.dirname(os.path.abspath(__file__))
    cmd = "'%s/boar' serve -S '%s'" % (boarhome, repopath)
    return _connect_cmd(cmd)


def __get_ssh_command():
    ssh_cmd = None
    devnull = open(os.devnull, "w")
    def cmd_exists(cmd):
        try:
            subprocess.call(cmd, stdout = devnull, stderr = devnull)
            return True
        except OSError:
            return False

    ssh_candidates = "ssh", "plink.exe", "ssh.exe"
    for candidate in ssh_candidates:
        if cmd_exists(candidate):
            ssh_cmd = candidate
            break
    if not ssh_cmd:
        raise UserError("No ssh command found (tried: %s)" % (", ".join(ssh_candidates)))
    return ssh_cmd
