import jsonrpc
import md5
import base64

def md5sum(data):
    m = md5.new()
    m.update(data)
    return m.hexdigest()

server = jsonrpc.ServerProxy(jsonrpc.JsonRpc20(), jsonrpc.TransportTcpIp(addr=("127.0.0.1", 50000), timeout=60.0))

print server.hello()
"""
print server.front.get_all_session_ids()
print "Initing co"
server.front.init_co(10)
print "Inited co"
while True:
    info = server.front.get_next_file()
    if not info:
        break
    print info['filename'], info['size'], info['md5sum']
    data = base64.b64decode(info['data_b64'])
    print md5sum(data) == info['md5sum']
"""
