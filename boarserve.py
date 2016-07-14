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

from blobrepo import repository
import os
import SocketServer
import front
import sys
import socket

from boar_exceptions import *
from common import warn

import jsonrpc

def ping():
    return "pong"

class PipedBoarServer:
    def __init__(self, repopath, from_client, to_client):
        self.repopath = repopath
        self.handler = jsonrpc.RpcHandler()
        self.handler.register_function(ping, "ping")
        self.handler.register_function(self.initialize, "initialize")
        self.server = jsonrpc.BoarMessageServer(from_client, to_client, self.handler)

    def initialize(self):
        self.repo = repository.Repo(self.repopath)
        fr = front.Front(self.repo)
        self.handler.register_instance(fr, "front")

    def serve(self):
        try:
            self.server.serve()
        finally:
            self._cleanup()

    def _cleanup(self):
        if self.repo.repo_mutex.is_locked():
            self.repo.repo_mutex.release()

def init_stdio_server(repopath):
    """This creates a boar server that uses sys.stdin/sys.stdout to
    communicate with the client. The function also hides the real
    sys.stdin and sys.stdout to prevent any print commands from
    accidentially corrupting the communication. (sys.stdout is
    directed to sys.stderr, sys.stdin is set to None)"""
    server = PipedBoarServer(repopath, sys.stdin, sys.stdout)
    sys.stdin = None
    sys.stdout = sys.stderr
    return server

class ForkingTCPServer(SocketServer.ForkingMixIn, SocketServer.TCPServer):
    pass

def run_socketserver(repopath, address, port):
    repository.Repo(repopath) # Just check if the repo path is valid
    class BoarTCPHandler(SocketServer.BaseRequestHandler):
        def handle(self):
            to_client = self.request.makefile(mode="wb")
            from_client = self.request.makefile(mode="rb")
            PipedBoarServer(repopath, from_client, to_client).serve()

    if "fork" not in dir(os):
        warn("Your operating system does not support the 'fork()' system call. This server will only be able to handle one client at a time. Please see the manual on how to set up a server on your operating system to handle multiple clients.")
        server = SocketServer.TCPServer((address, port), BoarTCPHandler)
    else:
        server = ForkingTCPServer((address, port), BoarTCPHandler)

    ip = server.socket.getsockname()[0]
    if ip == "0.0.0.0":
        ip = socket.gethostname()
    print "Serving repository %s as boar://%s:%s/" % (repopath, ip, port)
    server.serve_forever()
