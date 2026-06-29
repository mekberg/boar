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

"""Backwards-compatibility shim for the deduplication extension.

The deduplication primitives (RollingChecksum, IntegerSet, calc_rolling,
BlocksDB, ...) were historically provided by the C/Cython extension module
``cdedup``. They are now provided by the Rust/PyO3 extension ``rdedup``. This
module re-exports ``rdedup`` under the old name so that ``import cdedup`` and
``from cdedup import ...`` keep resolving to the implementation - independently
of import order, and regardless of whether ``deduplication`` was imported first.
"""

import sys

import rdedup

# Make ``cdedup`` *be* ``rdedup``: every attribute, and any
# ``from cdedup import X``, resolves to the rdedup implementation.
sys.modules[__name__] = rdedup
