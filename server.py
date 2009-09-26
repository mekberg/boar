import repository
import jsonrpc
import os
import front

def main():
    server = jsonrpc.Server(jsonrpc.JsonRpc20(), 
                            jsonrpc.TransportTcpIp(timeout=60.0, addr=("127.0.0.1", 31415), 
                                                   logfunc=jsonrpc.log_file("myrpc.log")))

    repopath = os.getenv("REPO_PATH")
    if repopath == None:
        print "You need to set REPO_PATH"
        return
    repo = repository.Repo(repopath)
    fr = front.Front(repo)
    server.register_instance(fr, "front")
    server.serve()

main()

