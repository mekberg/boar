import simplejson as json
import md5
import base64
import types
import socket

def open_socket():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('',50000))
    s.listen(5)
    conn, addr = s.accept()
    print 'Got connection from', addr
    return conn

class Server:

    def __init__(self, conn):
        self.functions = {}
        self.input_buffer = ""
        self.conn = conn

    def recv(self):
        """Returns some data from the other side"""
        return self.conn.recv(1024)
        
    def send(self, msg):
        print "Sending msg:", msg
        self.conn.sendall(msg)

    
    def register_function(self, name, func):
        assert isinstance(name, types.StringType)
        self.functions[name] = func

    def serve(self):
        while True:
            self.serve_once()

    def serve_once(self):
        self.input_buffer += self.recv()
        try:
            recvd_obj = json.loads(self.input_buffer)
        except ValueError:
            # Not yet a full packet probably
            return
        print "Got message:", self.input_buffer
        self.input_buffer = ""
        id = None
        try:
            id = recvd_obj['id']
            method = recvd_obj['method']
            params = []
            if recvd_obj.has_key('params'):
                params = recvd_obj['params']
            handler = self.functions[method]
            result = handler(*params)
            response = {"result": result,
                        "id": id,
                        "jsonrpc": "2.0"}
        except Exception, err:
            print "Exception while handling:", type(err), err
            response = {"error": {"code": -32603,
                                  "message": str(err)},
                        "id": id,
                        "jsonrpc": "2.0"}

        msg = json.dumps(response)
        self.send(msg)


def hello():
    return "Hello there"

def main():
    server = Server(open_socket())
    server.register_function("hello", hello)
    server.serve()

main()
