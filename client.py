import jsonrpc
import md5
import base64
import re
def connect(url):
    
    m = re.match("avo://(.*?)/", url)
    assert m, "Not a valid avocado url"
    address = m.group(1)    
    server = jsonrpc.ServerProxy(jsonrpc.JsonRpc20(), 
                                 jsonrpc.TransportTcpIp(addr=(address, 50000), timeout=60.0, limit=2**16))
    return server.front

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
