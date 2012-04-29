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

def connect(url):
    m = re.match("boar://(.*?)(:[0-9]+)?/", url)
    assert m, "Not a valid boar url"
    address = m.group(1)    
    port = 50000
    if m.group(2):
        port = int(m.group(2)[1:])
    #print "Connecting to '%s' on port %s" % (address, port)
    server = jsonrpc.ServerProxy(jsonrpc.JsonRpc20(), 
                                 jsonrpc.TransportTcpIp(addr=(address, port), 
                                                        timeout=60.0, limit=2**16))
    return server.front


import subprocess, time

def connect_ssh(url):
    print "Connecting with command"
    url_match = re.match("boar\+ssh://(.*)@([^/]+)(/.*)", url)
    assert url_match, "Not a valid Boar URL:" + url
    user, host, path = url_match.groups()
    cmd = "ssh '%s'@'%s' python hg/boar-contrib/server.py '%s'" % (user, host, path)
    print user, host, path
    p = subprocess.Popen(cmd, 
                         shell = True, 
                         stdout = subprocess.PIPE, 
                         stdin = subprocess.PIPE, 
                         stderr = open("output-server.txt", "w"))
    if p.poll() != None:
        print "*** Command failed: ", cmd
        sys.exit(1)
    else:
        print "*** Command running"
    server = jsonrpc.ServerProxy(jsonrpc.JsonRpc20(), 
                                 jsonrpc.TransportStream(p.stdout, p.stdin))
    assert server.front.ping() == "pong"
    return server.front


