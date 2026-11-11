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

"""Shared-key authentication and encryption for the boar TCP transport.

Both ends hold the same 256-bit key (see "boar mkkey"). The key never
travels over the wire. A connection starts with a cleartext handshake
that proves both ends know the key and derives fresh per-connection
keys; after that, everything is carried in authenticated encrypted
records, on top of which the ordinary boar message protocol runs
unchanged.

Handshake
---------

    client -> server   "boar" | version 7 | method (1 byte) | Pc (32 bytes)
    server -> client   "boar" | version 7 | status (1 byte) | Ps (32 bytes)
                       | tag (32 bytes)

"boar" | version are two big-endian uint32, the same leader as an
ordinary boar message header (which has version 6). That makes the two
protocols tell each other apart cleanly: a pre-encryption server
answers a hello with its usual "incompatible version" reply, and a
pre-encryption client gets a version 7 leader, which it reports as an
incompatible protocol version.

Pc and Ps are the public halves of X25519 key pairs that each side
makes up for this connection only, and throws away afterwards. With K
being the shared key, and S the X25519 shared secret of the two pairs:

    tag  = BLAKE2b(key=K, person="boar-auth-server", Pc | Ps | S)
    Kc2s = BLAKE2b(key=K, person="boar-key-c2s",     Pc | Ps | S)
    Ks2c = BLAKE2b(key=K, person="boar-key-s2c",     Pc | Ps | S)

The tag proves to the client that the server knows K. The client
proves itself implicitly: without K it cannot produce a single valid
record, and the server drops the connection at the first invalid one.

K alone provides all the authentication; the X25519 exchange is there
for forward secrecy. Since S can not be computed from what goes over
the wire, someone who records traffic and later obtains K still can
not decrypt it. (Someone who already has K can of course connect, or
impersonate the server to a connecting client.)

Records
-------

    length (uint32, big-endian) | ChaCha20-Poly1305-IETF ciphertext

"length" is the ciphertext length (plaintext + 16 byte tag), and is
also fed to the AEAD as associated data. The nonce is the record's
sequence number in that direction, so records can not be replayed,
reordered, dropped or moved between directions or connections.

The cipher and X25519 come from libsodium, through the PyNaCl package. It is
only needed for encrypted TCP connections; everything else in boar
works without it.
"""

import hashlib
import hmac
import os
import struct

from boar_exceptions import UserError, ConnectionLost

MAGIC = 0x626f6172 # "boar", same as jsonrpc.HEADER_MAGIC
LEGACY_VERSION = 6 # The version field of a cleartext boar message header
HELLO_VERSION = 7
LEADER_SIZE = 8

METHOD_SHARED_KEY = 1

STATUS_OK = 0
STATUS_NO_KEY = 1             # The server has no key, it only speaks cleartext
STATUS_UNKNOWN_METHOD = 2
STATUS_BAD_HELLO = 3

KEY_SIZE = 32
PUBLIC_SIZE = 32 # An X25519 public key
TAG_SIZE = 32
CLIENT_HELLO_SIZE = LEADER_SIZE + 1 + PUBLIC_SIZE
SERVER_HELLO_SIZE = LEADER_SIZE + 1 + PUBLIC_SIZE + TAG_SIZE

RECORD_MAX_PLAINTEXT = 2**16
AEAD_OVERHEAD = 16

KEYFILE_ENV = "BOAR_KEYFILE"
ALLOW_INSECURE_ENV = "BOAR_ALLOW_INSECURE"


class ServerSpeaksCleartextOnly(Exception):
    """The server did not accept an encrypted connection, either because it
    predates encryption or because it has been started without a key."""


def _aead():
    try:
        import nacl.bindings
    except ImportError:
        raise UserError("Encrypted connections require the PyNaCl package (try 'pip install pynacl')")
    return nacl.bindings


def require_cipher():
    """Raise a UserError if encrypted connections are unavailable."""
    _aead()


def generate_key():
    return os.urandom(KEY_SIZE)


def write_keyfile(path, key = None):
    """Create a new key file. It will not overwrite an existing file,
    and is created readable by the owner only."""
    if key is None:
        key = generate_key()
    assert len(key) == KEY_SIZE
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise UserError("File already exists: %s" % path)
    except OSError as e:
        raise UserError("Could not create key file: %s" % e)
    with os.fdopen(fd, "w") as f:
        f.write(key.hex() + "\n")


def read_keyfile(path):
    try:
        with open(path, "r") as f:
            text = f.read(1000)
    except (OSError, UnicodeDecodeError) as e:
        raise UserError("Could not read key file: %s" % e)
    try:
        key = bytes.fromhex(text.strip())
    except ValueError:
        key = b""
    if len(key) != KEY_SIZE:
        raise UserError("Not a valid boar key file: %s (create one with 'boar mkkey')" % path)
    return key


def _new_keypair():
    """Returns a fresh X25519 key pair as (secret, public)."""
    secret = os.urandom(32)
    return secret, _aead().crypto_scalarmult_base(secret)


def _session_secrets(key, client_public, server_public, my_secret, their_public):
    """Returns (server tag, client-to-server key, server-to-client key).
    Raises ValueError if the public key of the other side is bogus."""
    try:
        shared = _aead().crypto_scalarmult(my_secret, their_public)
    except Exception:
        raise ValueError("Invalid public key")
    material = client_public + server_public + shared
    return tuple(hashlib.blake2b(material, digest_size = 32, key = key, person = purpose).digest()
                 for purpose in (b"boar-auth-server", b"boar-key-c2s", b"boar-key-s2c"))


def _read_exactly(stream, n):
    data = stream.read(n)
    if data is None or len(data) != n:
        raise ConnectionLost("Transport stream closed by other side.")
    return data


class SecureWriter(object):
    """A writable binary file-like object that encrypts everything
    written to it before passing it on to the underlying stream."""

    mode = "wb"

    def __init__(self, stream, key):
        self.stream = stream
        self.key = key
        self.aead = _aead()
        self.seq = 0
        self.buffer = bytearray()

    def _send_record(self, plaintext):
        length = struct.pack("!I", len(plaintext) + AEAD_OVERHEAD)
        nonce = struct.pack("!IQ", 0, self.seq)
        self.seq += 1
        # A single write, or the length would travel in a packet of its own
        self.stream.write(length + self.aead.crypto_aead_chacha20poly1305_ietf_encrypt(
            bytes(plaintext), length, nonce, self.key))

    def write(self, data):
        self.buffer += data
        while len(self.buffer) >= RECORD_MAX_PLAINTEXT:
            self._send_record(self.buffer[:RECORD_MAX_PLAINTEXT])
            del self.buffer[:RECORD_MAX_PLAINTEXT]
        return len(data)

    def flush(self):
        if self.buffer:
            self._send_record(self.buffer)
            del self.buffer[:]
        self.stream.flush()

    def close(self):
        try:
            self.flush()
        except (OSError, ValueError):
            pass # The other side is already gone, nothing to be done
        self.stream.close()


class SecureReader(object):
    """A readable binary file-like object that yields the decrypted
    contents of the records arriving on the underlying stream."""

    mode = "rb"

    def __init__(self, stream, key):
        self.stream = stream
        self.key = key
        self.aead = _aead()
        self.seq = 0
        self.buffer = bytearray()
        self.eof = False

    def _fill(self):
        """Read one record into the buffer. Returns False at end of stream."""
        if self.eof:
            return False
        header = self.stream.read(4)
        if not header:
            self.eof = True
            return False
        if len(header) != 4:
            raise ConnectionLost("Encrypted stream was cut off")
        length, = struct.unpack("!I", header)
        if not AEAD_OVERHEAD < length <= RECORD_MAX_PLAINTEXT + AEAD_OVERHEAD:
            raise ConnectionLost("Encrypted stream is corrupt")
        ciphertext = self.stream.read(length)
        if len(ciphertext) != length:
            raise ConnectionLost("Encrypted stream was cut off")
        nonce = struct.pack("!IQ", 0, self.seq)
        self.seq += 1
        try:
            self.buffer += self.aead.crypto_aead_chacha20poly1305_ietf_decrypt(
                ciphertext, header, nonce, self.key)
        except Exception:
            # Wrong key at the other end, or tampering
            raise ConnectionLost("Encrypted stream failed authentication")
        return True

    def read(self, n = -1):
        if n is None or n < 0:
            while self._fill():
                pass
            n = len(self.buffer)
        while len(self.buffer) < n and self._fill():
            pass
        data = bytes(self.buffer[:n])
        del self.buffer[:n]
        return data

    def peek(self, n = 0):
        if not self.buffer:
            self._fill()
        return bytes(self.buffer)

    def fileno(self):
        return self.stream.fileno()

    def close(self):
        self.stream.close()


class PrefixedReader(object):
    """Puts some already consumed bytes back in front of a stream."""

    mode = "rb"

    def __init__(self, prefix, stream):
        self.prefix = prefix
        self.stream = stream

    def read(self, n = -1):
        if not self.prefix:
            return self.stream.read(n)
        if n is None or n < 0:
            data, self.prefix = self.prefix, b""
            return data + self.stream.read()
        data, self.prefix = self.prefix[:n], self.prefix[n:]
        if len(data) < n:
            data += self.stream.read(n - len(data))
        return data

    def peek(self, n = 0):
        return self.prefix or self.stream.peek(n)

    def fileno(self):
        return self.stream.fileno()

    def close(self):
        self.stream.close()


def client_handshake(from_server, to_server, key):
    """Set up an encrypted connection from the client side. Returns
    the tuple (from_server, to_server) of encrypted streams. Raises
    ServerSpeaksCleartextOnly if the server can't do encryption, and
    UserError if the server does not have the same key as we do."""
    assert len(key) == KEY_SIZE
    require_cipher()
    client_secret, client_public = _new_keypair()
    to_server.write(struct.pack("!IIB", MAGIC, HELLO_VERSION, METHOD_SHARED_KEY) + client_public)
    to_server.flush()
    try:
        magic, version = struct.unpack("!II", _read_exactly(from_server, LEADER_SIZE))
    except (ConnectionLost, OSError):
        raise UserError("The server closed the connection during the encryption handshake")
    if magic != MAGIC:
        raise UserError("The server does not seem to be a boar server")
    if version == LEGACY_VERSION:
        raise ServerSpeaksCleartextOnly("The server is too old to support encrypted connections")
    if version != HELLO_VERSION:
        raise UserError("The server uses an incompatible protocol version (%s)" % version)
    reply = _read_exactly(from_server, SERVER_HELLO_SIZE - LEADER_SIZE)
    status = reply[0]
    server_public = reply[1:1 + PUBLIC_SIZE]
    tag = reply[1 + PUBLIC_SIZE:]
    if status == STATUS_NO_KEY:
        raise ServerSpeaksCleartextOnly("The server is not configured for encrypted connections")
    if status != STATUS_OK:
        raise UserError("The server refused the encryption handshake (status %s)" % status)
    try:
        expected_tag, c2s_key, s2c_key = _session_secrets(
            key, client_public, server_public, client_secret, server_public)
    except ValueError:
        expected_tag = None
    if expected_tag is None or not hmac.compare_digest(tag, expected_tag):
        raise UserError("Authentication failed: the server does not have the same key as you do")
    return SecureReader(from_server, s2c_key), SecureWriter(to_server, c2s_key)


def _reject(to_client, status):
    try:
        to_client.write(struct.pack("!IIB", MAGIC, HELLO_VERSION, status) +
                        bytes(PUBLIC_SIZE + TAG_SIZE))
        to_client.flush()
    except OSError:
        pass


def server_handshake(from_client, to_client, key, allow_insecure):
    """Greet a newly connected client. Returns the tuple (from_client,
    to_client, encrypted) with the streams to use for the rest of the
    connection, or None if the client was turned away.

    'key' may be None, in which case only cleartext connections are
    possible. Cleartext connections are only accepted if
    'allow_insecure' is true."""
    assert key is None or len(key) == KEY_SIZE
    assert key is not None or allow_insecure
    try:
        leader = _read_exactly(from_client, LEADER_SIZE)
    except (ConnectionLost, OSError):
        return None
    magic, version = struct.unpack("!II", leader)
    if magic != MAGIC:
        return None
    if version != HELLO_VERSION:
        # A cleartext client. Its first message has already started.
        if allow_insecure:
            return PrefixedReader(leader, from_client), to_client, False
        # This is the best we can do to make an old client say
        # something sensible ("incompatible protocol version").
        _reject(to_client, STATUS_OK)
        return None
    try:
        hello = _read_exactly(from_client, CLIENT_HELLO_SIZE - LEADER_SIZE)
    except (ConnectionLost, OSError):
        return None
    method, client_public = hello[0], hello[1:]
    if key is None:
        _reject(to_client, STATUS_NO_KEY)
        return None
    if method != METHOD_SHARED_KEY:
        _reject(to_client, STATUS_UNKNOWN_METHOD)
        return None
    server_secret, server_public = _new_keypair()
    try:
        tag, c2s_key, s2c_key = _session_secrets(
            key, client_public, server_public, server_secret, client_public)
    except ValueError:
        _reject(to_client, STATUS_BAD_HELLO)
        return None
    to_client.write(struct.pack("!IIB", MAGIC, HELLO_VERSION, STATUS_OK) + server_public + tag)
    to_client.flush()
    return SecureReader(from_client, c2s_key), SecureWriter(to_client, s2c_key), True
