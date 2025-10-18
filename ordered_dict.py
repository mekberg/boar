"""Compatibility wrapper around :class:`collections.OrderedDict`.

The original project bundled a pure-Python backport for Python 2.x. Since
Boar now targets Python 3.8 and newer, the standard library implementation is
always available, so this module simply re-exports it for existing imports.
"""

from collections import OrderedDict

__all__ = ["OrderedDict"]
