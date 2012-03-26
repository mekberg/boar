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

class BoarServer:
    def __init__(self, repopath, port = 50000):
        self.repopath = repopath
        self.server = jsonrpc.Server(jsonrpc.JsonRpc20(), 
                                     jsonrpc.TransportTcpIp(timeout=60.0, 
                                                            addr=("0.0.0.0", port)))
    def serve(self):
        repo = repository.Repo(self.repopath)
        fr = front.Front(repo)
        self.server.register_instance(fr, "front")        
        self.server.serve()

class ThreadedBoarServer(BoarServer):
    def __init__(self, repopath, port = 50000):
        BoarServer.__init__(self, repopath, port)

    def serve(self):
        def super_serve():
            BoarServer.serve(self)
        self.serverThread = threading.Thread(target = super_serve)
        self.serverThread.setDaemon(True)
        self.serverThread.start()

def main():
    repopath = os.getenv("REPO_PATH")
    if repopath == None:
        print "You need to set REPO_PATH"
        return
    server = BoarServer(repopath)
    print "Serving"
    pid = server.serve()

if __name__ == "__main__":
    main()
