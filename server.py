import repository
import jsonrpc
import os
import front

def main():
    server = jsonrpc.Server(jsonrpc.JsonRpc20(), 
                            jsonrpc.TransportTcpIp(timeout=60.0, addr=("0.0.0.0", 50000)))

    repopath = os.getenv("REPO_PATH")
    if repopath == None:
        print "You need to set REPO_PATH"
        return
    repo = repository.Repo(repopath)
    fr = front.Front(repo)
    server.register_instance(fr, "front")
    server.serve()

main()

