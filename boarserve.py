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
from common import FakeFile

class StdioBoarServer:
    """This is a boar server that uses stdin/stdout to communicate
    with the client. When initialized, this server hides the real
    sys.stdin and sys.stdout so that print commands can not
    accidentially corrupt the communication."""

    def __init__(self, repopath):
        self.repopath = repopath
        cmd_stdin = sys.stdin
        cmd_stdout = sys.stdout 
        sys.stdin = None
        sys.stdout = sys.stderr
        self.server = jsonrpc.Server(jsonrpc.JsonRpc20(), 
                                     jsonrpc.TransportStream(cmd_stdin, cmd_stdout))

    def serve(self):
        repo = repository.Repo(self.repopath)
        fr = front.Front(repo)
        self.server.register_instance(fr, "front")        
        self.server.serve()


def main():
    repopath = unicode(sys.argv[1])
    server = StdioBoarServer(repopath)
    server.serve()

if __name__ == "__main__":
    try:
        main()
    except Exception, e:
        #open("/tmp/server-crash.txt", "a").write(repr(e))
        raise

