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

    def register_function(self, name, func):
        assert isinstance(name, types.StringType)
        self.functions[name] = func

    def serve(self):
        while True:
            self.serve_once()

    def _poll_for_message(self):
        self.input_buffer += self.conn.recv(1024)
        try:
            recvd_obj = json.loads(self.input_buffer)
        except ValueError:
            # Not yet a full packet probably
            return None
        print "Got message:", self.input_buffer
        self.input_buffer = ""
        return recvd_obj

    def _handle_msg(self, msg):
        id = msg['id']
        method = msg['method']
        params = []
        if msg.has_key('params'):
            params = msg['params']
        handler = self.functions[method]
        result = handler(*params)
        return id, result

    def serve_once(self):
        recvd_obj = self._poll_for_message()
        if recvd_obj == None:
            return

        try:
            id = None # In case of an early exception below
            id, result = self._handle_msg(recvd_obj)
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
        self.conn.sendall(msg)


def hello():
    return "Hello there"

def main():
    server = Server(open_socket())
    server.register_function("hello", hello)
    server.serve()

main()
