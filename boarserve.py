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

from blobrepo import repository
import jsonrpc
import os, time, threading
import front
import sys
import socket

from boar_exceptions import *

from common import FakeFile
from optparse import OptionParser

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
        repo = repository.Repo(self.repopath)
        fr = front.Front(repo)
        self.handler.register_instance(fr, "front")

    def serve(self):
        self.server.serve()
        
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

def run_socketserver(repopath, address, port):
    import SocketServer
    repository.Repo(repopath) # Just check if the repo path is valid
    class BoarTCPHandler(SocketServer.BaseRequestHandler, SocketServer.ForkingMixIn):
        def handle(self):
            to_client = self.request.makefile(mode="wb")
            from_client = self.request.makefile(mode="rb")
            PipedBoarServer(repopath, from_client, to_client).serve()
    server = SocketServer.TCPServer((address, port), BoarTCPHandler)
    ip = server.socket.getsockname()[0]
    if ip == "0.0.0.0":
        ip = socket.gethostname()
    print "Serving repository %s as boar+tcp://%s:%s/" % (repopath, ip, port)
    server.serve_forever()        

def main():
    args = sys.argv[1:]
    parser = OptionParser(usage="usage: boarserver.py [options] <repository path>")
    parser.add_option("-S", "--stdio-server", dest = "use_stdio", action="store_true",
                      help="Start a server that uses stdin/stdout as communication channels.")
    parser.add_option("-T", "--tcp-server", dest = "use_tcp", action="store_true",
                      help="Start a network server.")
    parser.add_option("-p", "--port", action="store", dest = "port", type="int", default=10001, metavar = "PORT",
                      help="The port that the network server will listen to (default: 10001)")
    parser.add_option("-a", "--address", dest = "address", metavar = "ADDR", default="",
                      help="The address that the network server will listen on (default: all interfaces)")
    if len(args) == 0:
        args = ["--help"]
    (options, args) = parser.parse_args(args)
    if len(args) != 1:
        raise UserError("Wrong number of arguments")
    repopath = unicode(args[0])
    if options.use_tcp:
        run_socketserver(repopath, options.address, options.port)
    elif options.use_stdio:
        server = init_stdio_server(repopath)
        server.serve()
    
        
if __name__ == "__main__":
    try:
        main()
    except Exception, e:
        print "*** Server encountered an exception ***"
        raise

