#!/usr/bin/env python
# -*- coding: utf-8 -*-

__version__ = "2008-08-31-beta"
__author__   = "Roland Koebler <rk(at)simple-is-better.org>"
__license__  = """Copyright (c) 2007-2008 by Roland Koebler (rk(at)simple-is-better.org)

Permission is hereby granted, free of charge, to any person obtaining
a copy of this software and associated documentation files (the
"Software"), to deal in the Software without restriction, including
without limitation the rights to use, copy, modify, merge, publish,
distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so, subject to
the following conditions:

The above copyright notice and this permission notice shall be included
in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE."""

#=========================================
#import

import sys, os
import struct
from boar_exceptions import *
from common import *
import traceback

#=========================================
# errors

#----------------------
# error-codes + exceptions

#JSON-RPC 2.0 error-codes
PARSE_ERROR           = -32700
INVALID_REQUEST       = -32600
METHOD_NOT_FOUND      = -32601
INVALID_METHOD_PARAMS = -32602  #invalid number/type of parameters
INTERNAL_ERROR        = -32603  #"all other errors"

#additional error-codes
PROCEDURE_EXCEPTION    = -32000
AUTHENTIFICATION_ERROR = -32001
PERMISSION_DENIED      = -32002
INVALID_PARAM_VALUES   = -32003

HANDLE_EXCEPTION   = -10002

#human-readable messages
ERROR_MESSAGE = {
    PARSE_ERROR           : "Parse error.",
    INVALID_REQUEST       : "Invalid Request.",
    METHOD_NOT_FOUND      : "Method not found.",
    INVALID_METHOD_PARAMS : "Invalid parameters.",
    INTERNAL_ERROR        : "Internal error.",

    PROCEDURE_EXCEPTION   : "Procedure exception.",
    AUTHENTIFICATION_ERROR : "Authentification error.",
    PERMISSION_DENIED   : "Permission denied.",
    INVALID_PARAM_VALUES: "Invalid parameter values."
    }
 
#----------------------
# exceptions

class RPCError(Exception):
    """Base class for rpc-errors."""

class RPCFault(RPCError):
    """RPC error/fault package received.
    
    This exception can also be used as a class, to generate a
    RPC-error/fault message.

    :Variables:
        - error_code:   the RPC error-code
        - error_string: description of the error
        - error_data:   optional additional information
                        (must be json-serializable)
    :TODO: improve __str__
    """
    def __init__(self, error_code, error_message, error_data=None):
        RPCError.__init__(self)
        self.error_code   = error_code
        self.error_message = error_message
        self.error_data   = error_data
        self.stack_trace = traceback.format_exc()

    def __str__(self):
        return repr(self)
    def __repr__(self):
        return( "<RPCFault %s: %s (%s)>\nRPCFault Traceback:\n%s" % (self.error_code, repr(self.error_message), repr(self.error_data), self.stack_trace) )

class RPCParseError(RPCFault):
    """Broken rpc-package. (PARSE_ERROR)"""
    def __init__(self, message=None, error_data=None):
        RPCFault.__init__(self, PARSE_ERROR, message, error_data)

class RPCInvalidRPC(RPCFault):
    """Invalid rpc-package. (INVALID_REQUEST)"""
    def __init__(self, message=None, error_data=None):
        RPCFault.__init__(self, INVALID_REQUEST, message, error_data)

class RPCMethodNotFound(RPCFault):
    """Method not found. (METHOD_NOT_FOUND)"""
    def __init__(self, message=None, error_data=None):
        RPCFault.__init__(self, METHOD_NOT_FOUND, message, error_data)

class RPCInvalidMethodParams(RPCFault):
    """Invalid method-parameters. (INVALID_METHOD_PARAMS)"""
    def __init__(self, message=None, error_data=None):
        RPCFault.__init__(self, INVALID_METHOD_PARAMS, message, error_data)

class RPCInternalError(RPCFault):
    """Internal error. (INTERNAL_ERROR)"""
    def __init__(self, message=None, error_data=None):
        RPCFault.__init__(self, INTERNAL_ERROR, message, error_data)

class RPCProcedureException(RPCFault):
    """Procedure exception. (PROCEDURE_EXCEPTION)"""
    def __init__(self, message=None, error_data=None):
        RPCFault.__init__(self, PROCEDURE_EXCEPTION, message, error_data)
class RPCAuthentificationError(RPCFault):
    """AUTHENTIFICATION_ERROR"""
    def __init__(self, message=None, error_data=None):
        RPCFault.__init__(self, AUTHENTIFICATION_ERROR, message, error_data)
class RPCPermissionDenied(RPCFault):
    """PERMISSION_DENIED"""
    def __init__(self, message=None, error_data=None):
        RPCFault.__init__(self, PERMISSION_DENIED, message, error_data)
class RPCInvalidParamValues(RPCFault):
    """INVALID_PARAM_VALUES"""
    def __init__(self, message=None, error_data=None):
        RPCFault.__init__(self, INVALID_PARAM_VALUES, message, error_data)


#=========================================

json = get_json_module()

#----------------------
#
def dictkeyclean(d):
    """Convert all keys of the dict 'd' to (ascii-)strings.

    :Raises: UnicodeEncodeError
    """
    new_d = {}
    for (k, v) in d.iteritems():
        new_d[str(k)] = v
    return new_d

#----------------------
# JSON-RPC 1.0

class DataSource:
    def bytes_left(self):
        """Return the number of bytes that remains to be read from
        this data source."""
        raise NotImplementedError()
    
    def read(self, n):
        """Reads and returns a number of bytes. May return fewer bytes
        than specified if there are no more bytes to read."""
        raise NotImplementedError()

class StreamDataSource(DataSource):
    def __init__(self, stream, data_size):
        self.stream = stream
        self.remaining = data_size

    def bytes_left(self):
        return self.remaining

    def read(self, n):
        if self.remaining == 0:
            return ""
        bytes_to_read = min(n, self.remaining)
        data = self.stream.read(bytes_to_read)
        self.remaining -= bytes_to_read
        assert len(data) == bytes_to_read
        assert len(data) <= n
        assert self.remaining >= 0
        return data

class FileDataSource(DataSource):
    def __init__(self, fo, data_size):
        self.fo = fo
        self.remaining = data_size
        if self.remaining == 0:
            self.fo.close()

    def bytes_left(self):
        return self.remaining

    def read(self, n = None):
        if n == None:
            n = self.remaining
        if self.remaining == 0:
            return ""
        bytes_to_read = min(n, self.remaining)
        data = self.fo.read(bytes_to_read)
        self.remaining -= bytes_to_read
        assert len(data) == bytes_to_read
        assert len(data) <= n
        assert self.remaining >= 0
        if self.remaining == 0:
            self.fo.close()
        return data

#----------------------
# JSON-RPC 2.0

class JsonRpc20:
    """BOAR-JSON-RPC V2.0"""
    @staticmethod
    def dumps_request( method, params=(), id=0 ):
        """ Serialize a JSON-RPC-Request. Accepts a method name and parameters.
        """
        if not isinstance(method, (str, unicode)):
            raise TypeError('"method" must be a string (or unicode string).')
        if not isinstance(params, (tuple, list, dict)):
            raise TypeError("params must be a tuple/list/dict or None.")
        obj = { "jsonrpc": "2.0",
                "method": method,
                "params": params,
                "id": id }
        return json.dumps(obj)

    @staticmethod
    def dumps_response( result, id=None ):
        """Serialize a JSON-RPC-Response. The 'result' argument may be
        any serializable object."""
        obj = { "jsonrpc": "2.0",
                "result": result,
                "id": id }
        return json.dumps(obj)


    @staticmethod
    def dumps_error( error, id=None ):
        """serialize a JSON-RPC-Response-error, typically a RPCError instance."""
        obj = { "jsonrpc": "2.0",
                "error": {"code": error.error_code,
                          "message": error.error_message,
                          "data": error.error_data},
                "id": id }
        return json.dumps(obj)

    @staticmethod
    def loads_request( string ):
        """de-serialize a JSON-RPC Request/Notification

        :Returns:   | [method_name, params, id] or [method_name, params]
                    | params is a tuple/list or dict (with only str-keys)
                    | if id is missing, this is a Notification
        :Raises:    RPCParseError, RPCInvalidRPC, RPCInvalidMethodParams
        """
        try:
            data = json.loads(string)
        except ValueError, err:
            raise RPCParseError("No valid JSON. (%s)" % str(err))
        if not isinstance(data, dict):  raise RPCInvalidRPC("No valid RPC-package.")
        if "jsonrpc" not in data:       raise RPCInvalidRPC("""Invalid Response, "jsonrpc" missing.""")
        if not isinstance(data["jsonrpc"], (str, unicode)):
            raise RPCInvalidRPC("""Invalid Response, "jsonrpc" must be a string.""")
        if data["jsonrpc"] != "2.0":    raise RPCInvalidRPC("""Invalid jsonrpc version.""")
        if "method" not in data:        raise RPCInvalidRPC("""Invalid Request, "method" is missing.""")
        if not isinstance(data["method"], (str, unicode)):
            raise RPCInvalidRPC("""Invalid Request, "method" must be a string.""")
        if "params" not in data:        data["params"] = ()
        #convert params-keys from unicode to str
        elif isinstance(data["params"], dict):
            try:
                data["params"] = dictkeyclean(data["params"])
            except UnicodeEncodeError:
                raise RPCInvalidMethodParams("Parameter-names must be in ascii.")
        elif not isinstance(data["params"], (list, tuple)):
            raise RPCInvalidRPC("""Invalid Request, "params" must be an array or object.""")
        if not( len(data)==3 or ("id" in data and len(data)==4) ):
            raise RPCInvalidRPC("""Invalid Request, additional fields found.""")

        assert "id" in data, "JsonRPC notifications not supported"
        return data["method"], data["params"], data["id"]

    @staticmethod
    def loads_response( string, allowed_exceptions ):
        """de-serialize a JSON-RPC Response/error

        :Returns: | [result, id] for Responses
        :Raises:  | RPCFault+derivates for error-packages/faults, RPCParseError, RPCInvalidRPC
        """
        try:
            data = json.loads(string)
        except ValueError, err:
            raise RPCParseError("No valid JSON. (%s)" % str(err))
        if not isinstance(data, dict):  raise RPCInvalidRPC("No valid RPC-package.")
        if "jsonrpc" not in data:       raise RPCInvalidRPC("""Invalid Response, "jsonrpc" missing.""")
        if not isinstance(data["jsonrpc"], (str, unicode)):
            raise RPCInvalidRPC("""Invalid Response, "jsonrpc" must be a string.""")
        if data["jsonrpc"] != "2.0":    raise RPCInvalidRPC("""Invalid jsonrpc version.""")
        if "id" not in data:            raise RPCInvalidRPC("""Invalid Response, "id" missing.""")
        if "result" not in data:        data["result"] = None
        if "error"  not in data:        data["error"]  = None
        if len(data) != 4:              raise RPCInvalidRPC("""Invalid Response, additional or missing fields.""")

        #error
        if data["error"] is not None:
            if data["result"] is not None:
                raise RPCInvalidRPC("""Invalid Response, only "result" OR "error" allowed.""")
            if not isinstance(data["error"], dict): raise RPCInvalidRPC("Invalid Response, invalid error-object.")
            if "code" not in data["error"]  or  "message" not in data["error"]:
                raise RPCInvalidRPC("Invalid Response, invalid error-object.")
            if "data" not in data["error"]:  data["error"]["data"] = None
            if len(data["error"]) != 3:
                raise RPCInvalidRPC("Invalid Response, invalid error-object.")

            error_data = data["error"]["data"]
            message = data["error"]["message"]
            
            if   data["error"]["code"] == PARSE_ERROR:
                raise RPCParseError(message,error_data)
            elif data["error"]["code"] == INVALID_REQUEST:
                raise RPCInvalidRPC(message,error_data)
            elif data["error"]["code"] == METHOD_NOT_FOUND:
                raise RPCMethodNotFound(message,error_data)
            elif data["error"]["code"] == INVALID_METHOD_PARAMS:
                raise RPCInvalidMethodParams(message,error_data)
            elif data["error"]["code"] == INTERNAL_ERROR:
                raise RPCInternalError(message,error_data)
            elif data["error"]["code"] == PROCEDURE_EXCEPTION:
                raise RPCProcedureException(message,error_data)
            elif data["error"]["code"] == AUTHENTIFICATION_ERROR:
                raise RPCAuthentificationError(message,error_data)
            elif data["error"]["code"] == PERMISSION_DENIED:
                raise RPCPermissionDenied(message,error_data)
            elif data["error"]["code"] == INVALID_PARAM_VALUES:
                raise RPCInvalidParamValues(message,error_data)
            elif data["error"]["code"] == HANDLE_EXCEPTION:
                exception = None
                exception_obj = json.loads(data["error"]["data"])
                assert isinstance(exception_obj['message'], unicode)
                for exception_type in allowed_exceptions:
                    if exception_obj['module'] == exception_type.__module__ and \
                            exception_obj['name'] == exception_type.__name__:
                        exception = exception_type(exception_obj['message'])
                if not exception:
                    raise Exception("Unknown remote exception: %s" % data["error"]["data"])
                assert isinstance(exception, Exception)
                raise exception
            else:
                raise RPCFault(data["error"]["code"], data["error"]["message"], error_data)
        #result
        else:
            return data["result"], data["id"]

jsonrpc20 = JsonRpc20()

#=========================================
# transports

#----------------------
# transport-logging

import codecs
import time

t0 = time.time()

def log_dummy( message ):
    """dummy-logger: do nothing"""
    #print round(time.time() - t0, 2), message
    pass

def log_stdout( message ):
    """print message to STDOUT"""
    print message

def log_file( filename ):
    """return a logfunc which logs to a file (in utf-8)"""
    def logfile( message ):
        f = codecs.open( filename, 'a', encoding='utf-8' )
        f.write( message+"\n" )
        f.close()
    return logfile

def log_filedate( filename ):
    """return a logfunc which logs date+message to a file (in utf-8)"""
    def logfile( message ):
        f = codecs.open( filename, 'a', encoding='utf-8' )
        f.write( time.strftime("%Y-%m-%d %H:%M:%S ")+message+"\n" )
        f.close()
    return logfile

#----------------------

HEADER_SIZE=21
HEADER_MAGIC=0x626f6172 # "boar"
HEADER_VERSION=4

def pack_header(payload_size, has_binary_payload = False, binary_payload_size = 0L):
    assert binary_payload_size >= 0
    assert type(has_binary_payload) == bool
    header_str = struct.pack("!III?Q", HEADER_MAGIC, HEADER_VERSION, payload_size,\
                                 has_binary_payload, long(binary_payload_size))
    assert len(header_str) == HEADER_SIZE
    return header_str

def read_header(stream):
    leader = stream.read(8)
    if len(leader) != 8:
        raise ConnectionLost("Transport stream closed by other side.")
    magic_number, version_number = struct.unpack("!II", leader)

    if magic_number != HEADER_MAGIC:
        raise ConnectionLost("Garbled message stream: %s..." % repr(leader))

    if version_number != HEADER_VERSION:
        raise WrongProtocolVersion("Wrong message protocol version: Expected %s, got %s" % (HEADER_VERSION, version_number))

    header_data = stream.read(13)

    if len(header_data) != 13:
        raise ConnectionLost("Transport stream closed by other side after greeting.")

    payload_size, has_binary_payload, binary_payload_size = \
        struct.unpack("!I?Q", header_data)

    if not has_binary_payload:
        assert binary_payload_size == 0
        binary_payload_size = None
    return payload_size, binary_payload_size

class BoarMessageClient:
    """This class is the client end of a connection capable of passing
    opaque message strings and streamed data. 
    """
    def __init__( self, s_in, s_out, logfunc=log_dummy ):
        assert s_in and s_out
        self.s_in = s_in
        self.s_out = s_out
        self.call_count = 0

    def log(self, s):
        print s

    def close( self ):
        self.s_in.close()
        self.s_out.close()

    def __repr__(self):
        return "<JsonrpcClient, %s, %s>" % (self.s_in, self.s_out)
    
    def __send( self, string, datasource = None ):
        bin_length = 0
        if datasource:
            bin_length = datasource.bytes_left()
        header = pack_header(len(string), datasource != None, bin_length)
        self.s_out.write(header)
        self.s_out.write(string)
        if datasource:
            while datasource.bytes_left() > 0:
                self.s_out.write(datasource.read(2**14))
        self.s_out.flush()
        
    def __recv( self ):
        datasize, binary_data_size = read_header(self.s_in)
        data = self.s_in.read(datasize)
        if binary_data_size != None:            
            return data, StreamDataSource(self.s_in, binary_data_size)
        else:
            return data, None

    def sendrecv( self, string, data_source = None ):
        """send data + receive data + close"""
        self.__send( string, data_source )
        return self.__recv()


class BoarMessageServer:
    """This class is the server end of a connection capable of passing
    opaque message strings and streamed data. It is the responsibility
    of the given 'handler' object to make sense of the received
    messages and compose suitable replies.
    
    The 'handler' object must have a method named "handle" accepting
    two parameters. The first is the received message as a string, the
    other is a DataSource instance. The DataSource instance is only
    given if the message contains streamed data, otherwise it is
    None. The "handle" method must return either a string or a
    DataSource instance, which will be sent to the client.
    """
    def __init__( self, s_in, s_out, handler, logfunc=log_dummy ):
        assert s_in and s_out
        self.s_in = s_in
        self.s_out = s_out
        self.call_count = 0
        self.handler = handler

    def log(self, s):
        pass

    def close( self ):
        self.s_in.close()
        self.s_out.close()

    def __repr__(self):
        return "<BoarMessageServer, %s, %s>" % (self.s_in, self.s_out)
    
    def init_server(self):
        pass
    
    def __send_result(self, result):
        assert result != None
        if isinstance(result, DataSource):
            dummy_result = jsonrpc20.dumps_response(None)
            header = pack_header(len(dummy_result), True, result.bytes_left())
            self.s_out.write( header )
            self.s_out.write( dummy_result )
            while result.bytes_left() > 0:
                piece = result.read(2**14)
                self.s_out.write(piece)
        else:
            header = pack_header(len(result))
            self.s_out.write( header )
            self.s_out.write( result )
        self.s_out.flush()

    def serve(self):
        try:
            self.log( "BoarMessageServer.Serve(): connected")
            while 1:
                try:
                    datasize, binary_data_size = read_header(self.s_in)
                except WrongProtocolVersion, e:
                    self.__send_result("['Dummy message. The response header should tell the client that the server is of an incompatible version']")
                    break
                except ConnectionLost, e:
                    self.log("Disconnected: %s" % e)
                    break
                data = self.s_in.read(datasize)
                if binary_data_size != None:
                    incoming_data_source = StreamDataSource(self.s_in, binary_data_size)
                else:
                    incoming_data_source = None
                result = self.handler.handle(data, incoming_data_source)
                if incoming_data_source:
                    assert incoming_data_source.bytes_left() == 0,\
                        "The data source object must be exhausted by the handler."
                self.__send_result(result)
                self.call_count += 1
                if self.handler.dead:
                    break
        finally:
            #open("/tmp/call_count.txt", "w").write(str(self.call_count) + " calls\n")
            self.close()


#=========================================
# client side: server proxy

class ServerProxy:
    """RPC-client: server proxy

    A logical connection to a RPC server.

    Notifications and id-handling/multicall are not yet implemented.

    :Example:
        see module-docstring

    :TODO: verbose/logging?
    """
    def __init__( self, transport, allowed_exceptions ):
        """
        :Parameters:
            - transport: a Transport instance
            - allowed_exceptions: A list of all classes that are valid incoming exceptions.
        """
        #TODO: check parameters
        self.__transport = transport
        for exception_class in allowed_exceptions:
            assert isinstance(exception_class, type)
        self.allowed_exceptions = allowed_exceptions[:]
        self.active_datasource = None

    def __str__(self):
        return repr(self)
    def __repr__(self):
        return "<ServerProxy for %s>" % (self.__transport)

    def __req( self, methodname, args=None, kwargs=None, id=0 ):
        # JSON-RPC 2.0: only args OR kwargs allowed!
        if self.active_datasource:
            assert self.active_datasource.bytes_left() == 0, \
                "The data source must be exhausted before any more jsonrpc calls can be made."
        datasource = kwargs.get("datasource", None)

        if datasource:
            assert isinstance(datasource, DataSource)
            self.active_datasource = datasource
            del kwargs["datasource"]
        for arg in args:
            assert not isinstance(arg, DataSource), "DataSource must be a keyword argument"

        if len(args) > 0 and len(kwargs) > 0:
            raise ValueError("Only positional or named parameters are allowed!")
        if len(kwargs) == 0:
            req_str  = JsonRpc20.dumps_request( methodname, args, id )
        else:
            req_str  = JsonRpc20.dumps_request( methodname, kwargs, id )

        resp_str, result_data_source = self.__transport.sendrecv( req_str, datasource)
        if result_data_source:
            return result_data_source
        resp = JsonRpc20.loads_response( resp_str, self.allowed_exceptions)
        return resp[0]

    def __getattr__(self, name):
        # magic method dispatcher
        #  note: to call a remote object with an non-standard name, use
        #  result getattr(my_server_proxy, "strange-python-name")(args)
        return _method(self.__req, name)

# request dispatcher
class _method:
    """some "magic" to bind an RPC method to an RPC server.

    Supports "nested" methods (e.g. examples.getStateName).

    :Raises: AttributeError for method-names/attributes beginning with '_'.
    """
    def __init__(self, req, name):
        if name[0] == "_":  #prevent rpc-calls for proxy._*-functions
            raise AttributeError("invalid attribute '%s'" % name)
        self.__req  = req
        self.__name = name
    def __getattr__(self, name):
        if name[0] == "_":  #prevent rpc-calls for proxy._*-functions
            raise AttributeError("invalid attribute '%s'" % name)
        return _method(self.__req, "%s.%s" % (self.__name, name))
    def __call__(self, *args, **kwargs):
        return self.__req(self.__name, args, kwargs)

#=========================================
# server side: Server

class RpcHandler:
    def __init__( self, logfile=None ):
        """
        :Parameters:
            - logfile: file to log ("unexpected") errors to
        """
        #TODO: check parameters
        self.dead = False
        self.logfile = logfile
        if self.logfile is not None:    #create logfile (or raise exception)
            f = codecs.open( self.logfile, 'a', encoding='utf-8' )
            f.close()

        self.funcs = {}

    def log(self, message):
        """write a message to the logfile (in utf-8)"""
        if self.logfile is not None:
            f = codecs.open( self.logfile, 'a', encoding='utf-8' )
            f.write( time.strftime("%Y-%m-%d %H:%M:%S ")+message+"\n" )
            f.close()

    def register_instance(self, myinst, name=None):
        """Add all functions of a class-instance to the RPC-services.
        
        All entries of the instance which do not begin with '_' are added.

        :Parameters:
            - myinst: class-instance containing the functions
            - name:   | hierarchical prefix.
                      | If omitted, the functions are added directly.
                      | If given, the functions are added as "name.function".
        :TODO:
            - only add functions and omit attributes?
            - improve hierarchy?
        """
        for e in dir(myinst):
            if e[0][0] != "_":
                if name is None:
                    self.register_function( getattr(myinst, e) )
                else:
                    self.register_function( getattr(myinst, e), name="%s.%s" % (name, e) )
    def register_function(self, function, name=None):
        """Add a function to the RPC-services.
        
        :Parameters:
            - function: function to add
            - name:     RPC-name for the function. If omitted/None, the original
                        name of the function is used.
        """
        if name is None:
            self.funcs[function.__name__] = function
        else:
            self.funcs[name] = function

    def handle(self, rpcstr, incoming_data_source):
        """Handle a RPC-Request.

        :Parameters:
            - rpcstr: the received rpc-string
        :Returns: the data to send back or None if nothing should be sent back
        :Raises:  RPCFault (and maybe others)
        """
        #TODO: id
        assert not self.dead, "An exception has already killed the server - go away"
        try:
            req = JsonRpc20.loads_request( rpcstr )
            if len(req) == 2:
                raise RPCFault("JsonRPC notifications not supported")
            method, params, id = req
        except RPCFault, err:
            self.dead = True
            return JsonRpc20.dumps_error( err, id=None )
        except Exception, err:
            self.dead = True
            self.log( "%d (%s): %s" % (INTERNAL_ERROR, ERROR_MESSAGE[INTERNAL_ERROR], str(err)) )
            return JsonRpc20.dumps_error( RPCFault(INTERNAL_ERROR, ERROR_MESSAGE[INTERNAL_ERROR], repr(err)), id=None )
        
        if method not in self.funcs:
            self.dead = True
            return JsonRpc20.dumps_error( RPCFault(METHOD_NOT_FOUND, ERROR_MESSAGE[METHOD_NOT_FOUND], method), id )

        try:
            if isinstance(params, dict):
                if incoming_data_source:
                    params['datasource'] = incoming_data_source
                result = self.funcs[method]( **params )
            else:
                if incoming_data_source:     
                    result = self.funcs[method]( *params, **{'datasource': incoming_data_source} )
                else:
                    result = self.funcs[method]( *params )
            if isinstance(result, DataSource):
                return result

        except RPCFault, err:
            self.dead = True
            return JsonRpc20.dumps_error( err, id=None )
        except Exception, err:
            self.dead = True
            exception_string = json.dumps({'module': err.__class__.__module__,
                                           'name': err.__class__.__name__,
                                           'message': str(err)})
            return JsonRpc20.dumps_error( RPCFault(HANDLE_EXCEPTION, traceback.format_exc(), exception_string), id )

        try:
            return JsonRpc20.dumps_response( result, id )
        except Exception, err:
            self.dead = True
            self.log( "%d (%s): %s" % (INTERNAL_ERROR, ERROR_MESSAGE[INTERNAL_ERROR], str(err)) )
            return JsonRpc20.dumps_error( RPCFault(INTERNAL_ERROR, ERROR_MESSAGE[INTERNAL_ERROR]), id )



