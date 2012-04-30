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

import subprocess

def connect_cmd(cmd):
    p = subprocess.Popen(cmd, 
                         shell = True, 
                         stdout = subprocess.PIPE, 
                         stdin = subprocess.PIPE, 
                         stderr = open("output-server.txt", "w"))
    server = jsonrpc.ServerProxy(jsonrpc.JsonRpc20(), 
                                 jsonrpc.TransportStream(p.stdout, p.stdin))
    assert server.front.ping() == "pong"
    return server.front

def connect_ssh(url):
    url_match = re.match("boar\+ssh://(.*)@([^/]+)(/.*)", url)
    assert url_match, "Not a valid Boar URL:" + url
    user, host, path = url_match.groups()
    cmd = "ssh '%s'@'%s' python hg/boar-contrib/server.py '%s'" % (user, host, path)
    print user, host, path
    return connect_cmd(cmd)



