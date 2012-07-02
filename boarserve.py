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

from common import FakeFile

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

class TcpBoarServer:
    def __init__(self, repopath, port):
        self.repopath = repopath
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind((socket.gethostname(), port))
        
    
        
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

def run_tcp_server(repopath, port):
    listensocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    hostname = ""
    print "Hostname:", hostname
    listensocket.bind((hostname, port))
    listensocket.listen(1)
    while True:
        connection, client_address = listensocket.accept()
        if not os.fork():
            # Child - serve the request
            to_client = connection.makefile(mode="wb")
            from_client = connection.makefile(mode="rb")
            server = PipedBoarServer(repopath, from_client, to_client)
            server.serve()
            return
        else:
            # Parent - clean up
            connection.close()

def main():
    repopath = unicode(sys.argv[1])
    server = init_stdio_server(repopath)
    server.serve()
    #run_tcp_server(repopath, 10005)

if __name__ == "__main__":
    try:
        main()
    except Exception, e:
        print "*** Server encountered an exception ***"
        raise

