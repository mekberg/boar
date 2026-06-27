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

"""Pluggable, streaming (de)compression codecs for blob recipes.

A repository can be configured to store all blob data compressed with a
chosen algorithm. The algorithm name is recorded in each "compress"
recipe, so reading a blob only requires the matching codec to be
available - boar itself is algorithm agnostic and stores the data in the
algorithm's standard container format. It is the user's responsibility
to pick an algorithm they will still be able to decode later.

Every codec exposes two tiny streaming interfaces:

  compressor():  an object with
      .compress(data) -> bytes      # feed more uncompressed data
      .flush()        -> bytes      # finish, returning the last bytes

  decompressor(): an object with
      .decompress(data, max_length) -> bytes  # up to max_length bytes out
      .needs_input  (property, bool)          # True if more input is wanted
      .eof          (property, bool)          # True once the stream ended

The decompressor model matches the stdlib lzma/bz2 decompressors: feed
compressed input, repeatedly drain output (passing b"" as input) until
needs_input becomes True again, and stop when eof is True.
"""

from boar_exceptions import UserError

import zlib


# --- gzip (zlib) -----------------------------------------------------------

class _ZlibCompressor(object):
    def __init__(self, level=6):
        # wbits=31 selects the gzip container (16) plus the maximum
        # window (15), so the produced blobs are ordinary .gz streams.
        self._c = zlib.compressobj(level, zlib.DEFLATED, 31)

    def compress(self, data):
        return self._c.compress(data)

    def flush(self):
        return self._c.flush()


class _ZlibDecompressor(object):
    def __init__(self):
        self._d = zlib.decompressobj(31)
        self._tail = b""

    def decompress(self, data, max_length):
        assert max_length > 0
        self._tail = self._tail + data
        out = self._d.decompress(self._tail, max_length)
        self._tail = self._d.unconsumed_tail
        return out

    @property
    def eof(self):
        return self._d.eof

    @property
    def needs_input(self):
        return not self._tail


# --- xz (lzma) and bz2 -----------------------------------------------------

class _NativeDecompressor(object):
    """Adapter for the stdlib lzma/bz2 decompressors, which already buffer
    their input internally and expose needs_input/eof."""
    def __init__(self, raw):
        self._d = raw

    def decompress(self, data, max_length):
        assert max_length > 0
        return self._d.decompress(data, max_length)

    @property
    def eof(self):
        return self._d.eof

    @property
    def needs_input(self):
        return self._d.needs_input


def _lzma_compressor():
    import lzma
    return lzma.LZMACompressor()  # FORMAT_XZ container by default


def _lzma_decompressor():
    import lzma
    return _NativeDecompressor(lzma.LZMADecompressor())


def _bz2_compressor():
    import bz2
    return bz2.BZ2Compressor()


def _bz2_decompressor():
    import bz2
    return _NativeDecompressor(bz2.BZ2Decompressor())


# --- lz4 (frame format) ----------------------------------------------------

class _Lz4Compressor(object):
    def __init__(self):
        import lz4.frame
        self._c = lz4.frame.LZ4FrameCompressor()
        self._begun = False

    def __begin(self):
        if self._begun:
            return b""
        self._begun = True
        return self._c.begin()

    def compress(self, data):
        return self.__begin() + self._c.compress(data)

    def flush(self):
        # Ensure a valid (possibly empty) frame is produced even if no
        # data was ever fed.
        return self.__begin() + self._c.flush()


def _lz4_decompressor():
    import lz4.frame
    return _NativeDecompressor(lz4.frame.LZ4FrameDecompressor())


# --- registry --------------------------------------------------------------

class _Codec(object):
    def __init__(self, name, module, compressor_factory, decompressor_factory):
        self.name = name
        self._module = module          # importable module name, or None for builtins
        self._compressor = compressor_factory
        self._decompressor = decompressor_factory

    def available(self):
        if self._module is None:
            return True
        try:
            __import__(self._module)
            return True
        except ImportError:
            return False

    def compressor(self):
        return self._compressor()

    def decompressor(self):
        return self._decompressor()


_CODECS = {
    "gzip": _Codec("gzip", None, _ZlibCompressor, _ZlibDecompressor),
    "xz":   _Codec("xz", "lzma", _lzma_compressor, _lzma_decompressor),
    "bz2":  _Codec("bz2", "bz2", _bz2_compressor, _bz2_decompressor),
    "lz4":  _Codec("lz4", "lz4.frame", _Lz4Compressor, _lz4_decompressor),
}

# Aliases the CLI and recipes will accept, mapped to a canonical name.
_ALIASES = {
    "gz": "gzip",
    "zlib": "gzip",
    "lzma": "xz",
    "bzip2": "bz2",
}

KNOWN_ALGORITHMS = tuple(_CODECS.keys())


def canonical_name(name):
    """Return the canonical algorithm name for the given (possibly
    aliased, possibly mixed-case) name. Returns the lower-cased input
    unchanged if it is not recognised."""
    assert isinstance(name, str)
    key = name.strip().lower()
    return _ALIASES.get(key, key)


def is_known(name):
    return canonical_name(name) in _CODECS


def is_available(name):
    """True if the named algorithm is both known and its codec module can
    be imported in this environment."""
    canon = canonical_name(name)
    codec = _CODECS.get(canon)
    return bool(codec) and codec.available()


def get_codec(name):
    """Return the codec for the named algorithm. Raises UserError if the
    algorithm is unknown or its module is not installed."""
    canon = canonical_name(name)
    codec = _CODECS.get(canon)
    if codec is None:
        raise UserError("Unknown compression algorithm: %s (known: %s)" %
                        (name, ", ".join(sorted(_CODECS.keys()))))
    if not codec.available():
        raise UserError("The '%s' compression algorithm is not available - "
                        "the required module is not installed." % canon)
    return codec
