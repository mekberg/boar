# -*- coding: utf-8 -*-

# Copyright 2026 Mats Ekberg
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

import sys, os, unittest, tempfile, shutil, io, socket, struct, threading

if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import securestream
import jsonrpc
from boar_exceptions import UserError, ConnectionLost

try:
    import nacl.bindings
    have_crypto = True
except ImportError:
    have_crypto = False

KEY = bytes(range(32))
OTHER_KEY = bytes(range(1, 33))

def encrypt(key, *chunks):
    """Returns the wire bytes resulting from writing and flushing
    each of the given chunks."""
    wire = io.BytesIO()
    writer = securestream.SecureWriter(wire, key)
    for chunk in chunks:
        writer.write(chunk)
        writer.flush()
    return wire.getvalue()

def split_records(wire):
    records = []
    while wire:
        length, = struct.unpack("!I", wire[:4])
        records.append(wire[:4 + length])
        wire = wire[4 + length:]
    return records

class TestKeyfile(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix='testsecurestream_')
        self.path = os.path.join(self.tmpdir, "key")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def testRoundtrip(self):
        securestream.write_keyfile(self.path, KEY)
        self.assertEqual(securestream.read_keyfile(self.path), KEY)

    def testGeneratedKeysDiffer(self):
        other = os.path.join(self.tmpdir, "other")
        securestream.write_keyfile(self.path)
        securestream.write_keyfile(other)
        self.assertEqual(len(securestream.read_keyfile(self.path)), 32)
        self.assertNotEqual(securestream.read_keyfile(self.path), securestream.read_keyfile(other))

    @unittest.skipIf(os.name != "posix", "posix permissions only")
    def testPermissions(self):
        securestream.write_keyfile(self.path)
        self.assertEqual(os.stat(self.path).st_mode & 0o777, 0o600)

    def testNoOverwrite(self):
        securestream.write_keyfile(self.path, KEY)
        self.assertRaises(UserError, securestream.write_keyfile, self.path)
        self.assertEqual(securestream.read_keyfile(self.path), KEY)

    def testInvalid(self):
        self.assertRaises(UserError, securestream.read_keyfile, self.path) # missing
        for content in "", "hello", "ab" * 31, "ab" * 33, "zz" * 32:
            with open(self.path, "w") as f:
                f.write(content)
            self.assertRaises(UserError, securestream.read_keyfile, self.path)

class TestPrefixedReader(unittest.TestCase):
    def reader(self):
        return securestream.PrefixedReader(b"abc", io.BufferedReader(io.BytesIO(b"defgh")))

    def testRead(self):
        r = self.reader()
        self.assertEqual(r.read(2), b"ab")
        self.assertEqual(r.read(3), b"cde")
        self.assertEqual(r.read(2), b"fg")
        self.assertEqual(r.read(10), b"h")
        self.assertEqual(r.read(10), b"")

    def testReadAll(self):
        self.assertEqual(self.reader().read(), b"abcdefgh")
        self.assertEqual(self.reader().read(100), b"abcdefgh")

    def testPeek(self):
        r = self.reader()
        self.assertEqual(r.peek(4), b"abc")
        r.read(3)
        self.assertEqual(r.peek(4)[:4], b"defg")
        self.assertEqual(r.read(), b"defgh")

@unittest.skipUnless(have_crypto, "PyNaCl not installed")
class TestRecords(unittest.TestCase):
    def reader(self, wire, key = KEY):
        return securestream.SecureReader(io.BytesIO(wire), key)

    def testRoundtrip(self):
        r = self.reader(encrypt(KEY, b"hello", b" ", b"world"))
        self.assertEqual(r.read(3), b"hel")
        self.assertEqual(r.read(6), b"lo wor")
        self.assertEqual(r.read(100), b"ld")
        self.assertEqual(r.read(100), b"")

    def testReadAll(self):
        self.assertEqual(self.reader(encrypt(KEY, b"hello", b"world")).read(), b"helloworld")

    def testPeek(self):
        r = self.reader(encrypt(KEY, b"hello", b"world"))
        self.assertEqual(r.peek(4), b"hello")
        self.assertEqual(r.read(5), b"hello")
        self.assertEqual(r.peek(4), b"world")
        self.assertEqual(r.read(), b"world")
        self.assertEqual(r.peek(4), b"")

    def testLargeData(self):
        data = os.urandom(3 * securestream.RECORD_MAX_PLAINTEXT + 1234)
        wire = io.BytesIO()
        writer = securestream.SecureWriter(wire, KEY)
        for i in range(0, len(data), 10000):
            writer.write(data[i:i+10000])
        writer.flush()
        records = split_records(wire.getvalue())
        self.assertEqual(len(records), 4)
        for record in records:
            self.assertLessEqual(len(record), 4 + securestream.RECORD_MAX_PLAINTEXT + 16)
        self.assertEqual(self.reader(wire.getvalue()).read(), data)

    def testNothingWrittenWithoutData(self):
        self.assertEqual(encrypt(KEY, b"", b""), b"")

    def testIsEncrypted(self):
        plaintext = b"very secret words " * 100
        wire = encrypt(KEY, plaintext)
        self.assertNotIn(b"secret", wire)
        self.assertEqual(len(wire), len(plaintext) + 4 + 16)
        # Same plaintext, different position in stream -> different ciphertext
        r1, r2 = split_records(encrypt(KEY, b"same", b"same"))
        self.assertNotEqual(r1, r2)

    def testWrongKey(self):
        self.assertRaises(ConnectionLost, self.reader(encrypt(KEY, b"hello"), OTHER_KEY).read, 1)

    def testTampering(self):
        wire = encrypt(KEY, b"hello")
        for i in range(len(wire)):
            tampered = bytearray(wire)
            tampered[i] ^= 1
            self.assertRaises(ConnectionLost, self.reader(bytes(tampered)).read, 5)

    def testTruncation(self):
        wire = encrypt(KEY, b"hello")
        for i in range(1, len(wire)):
            self.assertRaises(ConnectionLost, self.reader(wire[:i]).read, 5)

    def testReplayReorderAndDrop(self):
        r1, r2, r3 = split_records(encrypt(KEY, b"one", b"two", b"three"))
        self.assertEqual(self.reader(r1 + r2 + r3).read(), b"onetwothree")
        for wire in (r1 + r1, r2 + r1, r1 + r3, r2):
            self.assertRaises(ConnectionLost, self.reader(wire).read)

    def testOversizedRecordRefused(self):
        wire = struct.pack("!I", 2**31) + b"x" * 100
        self.assertRaises(ConnectionLost, self.reader(wire).read, 1)

class Connection(object):
    """A socket pair with a server handshake running in a thread"""
    def __init__(self, server_key, allow_insecure):
        self.client_sock, self.server_sock = socket.socketpair()
        self.from_server = self.client_sock.makefile("rb")
        self.to_server = self.client_sock.makefile("wb")
        self.server_result = None
        def server():
            self.server_result = securestream.server_handshake(
                self.server_sock.makefile("rb"), self.server_sock.makefile("wb"),
                server_key, allow_insecure)
            if not self.server_result:
                self.server_sock.close()
        self.thread = threading.Thread(target = server)
        self.thread.start()

    def finish(self):
        self.thread.join(10)
        assert not self.thread.is_alive()
        return self.server_result

    def close(self):
        self.finish()
        self.client_sock.close()
        self.server_sock.close()

class TestHandshake(unittest.TestCase):
    def connect(self, server_key, allow_insecure = False):
        conn = Connection(server_key, allow_insecure)
        self.addCleanup(conn.close)
        return conn

    def legacyHello(self, conn):
        """Act like a client from before encryption was introduced"""
        message = b'{"jsonrpc": "2.0", "method": "ping", "params": [], "id": 0}'
        conn.to_server.write(jsonrpc.pack_header(len(message)) + message)
        conn.to_server.flush()
        return message

    @unittest.skipUnless(have_crypto, "PyNaCl not installed")
    def testSuccess(self):
        conn = self.connect(KEY)
        from_server, to_server = securestream.client_handshake(conn.from_server, conn.to_server, KEY)
        from_client, to_client, encrypted = conn.finish()
        self.assertTrue(encrypted)
        to_server.write(b"question")
        to_server.flush()
        self.assertEqual(from_client.read(8), b"question")
        to_client.write(b"answer")
        to_client.flush()
        self.assertEqual(from_server.read(6), b"answer")

    @unittest.skipUnless(have_crypto, "PyNaCl not installed")
    def testSessionKeysAreUnique(self):
        """The same data must never encrypt the same way twice"""
        wires = []
        for _ in range(2):
            conn = self.connect(KEY)
            _, to_server = securestream.client_handshake(conn.from_server, conn.to_server, KEY)
            conn.finish()
            to_server.write(b"hello")
            to_server.flush()
            wires.append(conn.server_sock.recv(1000))
        self.assertEqual(len(wires[0]), 5 + 4 + 16)
        self.assertNotEqual(wires[0], wires[1])

    @unittest.skipUnless(have_crypto, "PyNaCl not installed")
    def testDirectionsUseDifferentKeys(self):
        """A record must not be accepted if reflected back to its sender"""
        conn = self.connect(KEY)
        from_server, to_server = securestream.client_handshake(conn.from_server, conn.to_server, KEY)
        conn.finish()
        to_server.write(b"hello")
        to_server.flush()
        conn.server_sock.sendall(conn.server_sock.recv(1000))
        self.assertRaises(ConnectionLost, from_server.read, 5)

    @unittest.skipUnless(have_crypto, "PyNaCl not installed")
    def testWrongKey(self):
        conn = self.connect(KEY)
        with self.assertRaisesRegex(UserError, "Authentication failed"):
            securestream.client_handshake(conn.from_server, conn.to_server, OTHER_KEY)

    @unittest.skipUnless(have_crypto, "PyNaCl not installed")
    def testClientWithoutKeyCantTalk(self):
        """A client that ignores the server's proof and just talks is dropped"""
        conn = self.connect(KEY)
        _, public = securestream._new_keypair()
        conn.to_server.write(struct.pack("!IIB", securestream.MAGIC, securestream.HELLO_VERSION,
                                         securestream.METHOD_SHARED_KEY) + public)
        conn.to_server.flush()
        from_client, to_client, encrypted = conn.finish()
        self.assertTrue(encrypted)
        conn.from_server.read(securestream.SERVER_HELLO_SIZE)
        # Neither cleartext nor records made with another key gets through
        conn.to_server.write(self.legacyHello(conn) + encrypt(OTHER_KEY, b"hello"))
        conn.to_server.flush()
        self.assertRaises(ConnectionLost, from_client.read, 1)

    @unittest.skipUnless(have_crypto, "PyNaCl not installed")
    def testBogusPublicKeyRefused(self):
        """An all-zero public key would force a known shared secret"""
        conn = self.connect(KEY)
        conn.to_server.write(struct.pack("!IIB", securestream.MAGIC, securestream.HELLO_VERSION,
                                         securestream.METHOD_SHARED_KEY) + bytes(32))
        conn.to_server.flush()
        self.assertIsNone(conn.finish())
        self.assertEqual(conn.from_server.read()[8], securestream.STATUS_BAD_HELLO)

    @unittest.skipUnless(have_crypto, "PyNaCl not installed")
    def testForwardSecrecy(self):
        """Someone who has recorded everything on the wire, and later
        gets hold of the key, must still not be able to decrypt."""
        client_sock, server_sock = socket.socketpair()
        tap_sock, client_side = socket.socketpair() # The client talks through a wiretap
        for s in client_sock, server_sock, tap_sock, client_side:
            self.addCleanup(s.close)
        recorded = {"c2s": b"", "s2c": b""}
        def server():
            from_client, to_client, _ = securestream.server_handshake(
                server_sock.makefile("rb"), server_sock.makefile("wb"), KEY, False)
            assert from_client.read(6) == b"secret"
        def relay(src, dst, name, count):
            while len(recorded[name]) < count:
                data = src.recv(1000)
                recorded[name] += data
                dst.sendall(data)
        hello_c, hello_s = securestream.CLIENT_HELLO_SIZE, securestream.SERVER_HELLO_SIZE
        threads = [threading.Thread(target = server),
                   threading.Thread(target = relay, args = (tap_sock, client_sock, "c2s", hello_c + 4 + 6 + 16)),
                   threading.Thread(target = relay, args = (client_sock, tap_sock, "s2c", hello_s))]
        for t in threads:
            t.start()
        _, to_server = securestream.client_handshake(client_side.makefile("rb"), client_side.makefile("wb"), KEY)
        to_server.write(b"secret")
        to_server.flush()
        for t in threads:
            t.join(10)
            self.assertFalse(t.is_alive())
        # The eavesdropper knows the key and both public keys, but neither secret half.
        client_public = recorded["c2s"][9:hello_c]
        server_public = recorded["s2c"][9:9 + 32]
        record = recorded["c2s"][hello_c:]
        self.assertEqual(len(record), 4 + 6 + 16)
        eve_secret, _ = securestream._new_keypair()
        guesses = [securestream._session_secrets(KEY, client_public, server_public, eve_secret, p)[1]
                   for p in (client_public, server_public)]
        import hashlib
        for purpose in b"boar-key-c2s", b"boar-key-s2c":
            guesses.append(hashlib.blake2b(client_public + server_public, digest_size = 32,
                                           key = KEY, person = purpose).digest())
        for guess in guesses:
            self.assertRaises(ConnectionLost, securestream.SecureReader(io.BytesIO(record), guess).read)

    @unittest.skipUnless(have_crypto, "PyNaCl not installed")
    def testServerWithoutKey(self):
        conn = self.connect(None, allow_insecure = True)
        with self.assertRaisesRegex(securestream.ServerSpeaksCleartextOnly, "not configured"):
            securestream.client_handshake(conn.from_server, conn.to_server, KEY)
        self.assertIsNone(conn.finish())

    @unittest.skipUnless(have_crypto, "PyNaCl not installed")
    def testUnknownMethod(self):
        conn = self.connect(KEY)
        conn.to_server.write(struct.pack("!IIB", securestream.MAGIC, securestream.HELLO_VERSION, 99) + bytes(32))
        conn.to_server.flush()
        self.assertIsNone(conn.finish())
        reply = conn.from_server.read()
        self.assertEqual(reply[8], securestream.STATUS_UNKNOWN_METHOD)
        self.assertEqual(reply[9:], bytes(64))

    @unittest.skipUnless(have_crypto, "PyNaCl not installed")
    def testOldServer(self):
        """A server from before encryption answers anything unknown
        with a message bearing its own protocol version"""
        client_sock, server_sock = socket.socketpair()
        self.addCleanup(client_sock.close)
        self.addCleanup(server_sock.close)
        server_sock.sendall(jsonrpc.pack_header(5) + b"dummy")
        with self.assertRaisesRegex(securestream.ServerSpeaksCleartextOnly, "too old"):
            securestream.client_handshake(client_sock.makefile("rb"), client_sock.makefile("wb"), KEY)

    def testLegacyClientRefused(self):
        conn = self.connect(KEY)
        self.legacyHello(conn)
        self.assertIsNone(conn.finish())
        # The old client must see this as a protocol version mismatch
        self.assertRaises(jsonrpc.WrongProtocolVersion, jsonrpc.read_header, conn.from_server)

    def testLegacyClientAccepted(self):
        for key in KEY, None:
            conn = self.connect(key, allow_insecure = True)
            message = self.legacyHello(conn)
            from_client, to_client, encrypted = conn.finish()
            self.assertFalse(encrypted)
            # The message that the handshake had to peek at must be intact
            size, _, _ = jsonrpc.read_header(from_client)
            self.assertEqual(from_client.read(size), message)

    def testGarbageRefused(self):
        for garbage in b"", b"GET", b"GET / HTTP/1.0\r\n\r\n", struct.pack("!II", securestream.MAGIC, 7) + b"x":
            conn = self.connect(KEY, allow_insecure = True)
            conn.to_server.write(garbage)
            conn.to_server.flush()
            conn.client_sock.shutdown(socket.SHUT_WR)
            self.assertIsNone(conn.finish())

if __name__ == '__main__':
    unittest.main()
