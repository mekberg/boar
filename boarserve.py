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
import socketserver
import front
import sys
import socket

from boar_exceptions import *
from common import warn

import jsonrpc
import securestream

# The time a client has to prove that it knows the key (seconds)
HANDSHAKE_TIMEOUT = float(os.getenv("BOAR_TEST_HANDSHAKE_TIMEOUT", "30"))

def ping():
    return "pong"

class PipedBoarServer(object):
    def __init__(self, repopath, from_client, to_client):
        self.repopath = repopath
        self.repo = None
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
        if self.repo and self.repo.repo_mutex.is_locked():
            self.repo.repo_mutex.release()

def init_stdio_server(repopath):
    """This creates a boar server that uses sys.stdin/sys.stdout to
    communicate with the client. The function also hides the real
    sys.stdin and sys.stdout to prevent any print commands from
    accidentially corrupting the communication. (sys.stdout is
    directed to sys.stderr, sys.stdin is set to None)"""
    server = PipedBoarServer(repopath, sys.stdin.buffer, sys.stdout.buffer)
    sys.stdin = None
    sys.stdout = sys.stderr
    return server

if "fork" in dir(os):
    class ForkingTCPServer(socketserver.ForkingMixIn, socketserver.TCPServer):
        pass

def run_socketserver(repopath, address, port, key = None, allow_insecure = False):
    """Serve the repository over TCP. Clients must prove knowledge of
    'key' and all traffic is encrypted, unless 'allow_insecure' is
    true, in which case old-style cleartext connections are accepted
    as well. Without a key, only cleartext connections are possible."""
    assert key is not None or allow_insecure
    repository.Repo(repopath) # Just check if the repo path is valid
    class BoarTCPHandler(socketserver.BaseRequestHandler):
        def handle(self):
            to_client = self.request.makefile(mode="wb")
            from_client = self.request.makefile(mode="rb")
            peer = "%s:%s" % self.client_address[:2]
            # Don't let connections that have not shown that they know
            # the key hang around. They tie up a server process each,
            # and there is a limit on how many of those there can be.
            self.request.settimeout(HANDSHAKE_TIMEOUT)
            authenticated = []
            def on_authenticated():
                authenticated.append(True)
                self.request.settimeout(None)
            try:
                streams = securestream.server_handshake(from_client, to_client, key, allow_insecure,
                                                        on_authenticated)
            except OSError:
                streams = None
            if not streams:
                warn("Rejected connection from %s" % peer)
                return
            from_client, to_client, encrypted = streams
            if not encrypted:
                warn("Client %s is using an insecure (cleartext) connection" % peer)
                on_authenticated() # This is as authenticated as it gets
            try:
                PipedBoarServer(repopath, from_client, to_client).serve()
            except ConnectionLost as e:
                # Typically a client with the wrong key
                warn("Dropped connection from %s: %s" % (peer, e))
            except OSError as e:
                if authenticated:
                    raise
                warn("Dropped unauthenticated connection from %s: %s" % (peer, e))

    # Allow the server to be restarted immediately
    socketserver.TCPServer.allow_reuse_address = True
    if "fork" not in dir(os):
        warn("Your operating system does not support the 'fork()' system call. This server will only be able to handle one client at a time. Please see the manual on how to set up a server on your operating system to handle multiple clients.")
        server = socketserver.TCPServer((address, port), BoarTCPHandler)
    else:
        server = ForkingTCPServer((address, port), BoarTCPHandler)

    ip = server.socket.getsockname()[0]
    if ip == "0.0.0.0":
        ip = socket.gethostname()
    if key is None:
        warn("This server has no authentication or encryption. Anyone who can connect to it can read and modify the repository.")
    elif allow_insecure:
        warn("This server accepts insecure connections. Anyone who can connect to it can read and modify the repository.")
    print("Serving repository %s as boar://%s:%s/" % (repopath, ip, port), flush=True)
    server.serve_forever()
