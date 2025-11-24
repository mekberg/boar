# -*- coding: utf-8 -*-
#
# Copyright 2024 Mats Ekberg
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

"""Standalone helper for scanning files and computing checksums."""

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Iterable, List, Optional

from boar_exceptions import UserError
from common import checksum_file, uabspath


class FileScanner(object):
    """Collects checksum and stat data for files and directories."""

    def __init__(self, paths: Iterable[str], threads: int = 1, relative_to: Optional[str] = None, skip: Optional[Iterable[str]] = None):
        if isinstance(paths, str):
            paths = [paths]
        if threads is None:
            threads = 1
        if not isinstance(threads, int) or threads < 1:
            raise UserError("Thread count must be a positive integer")
        self.threads = threads
        self.relative_to = self._normalize_base(relative_to)
        self.skip = set(skip or [])
        self._files = tuple(self._expand_paths(list(paths)))
        self._results: Dict[str, Dict[str, object]] = {}

    def _normalize_base(self, base: Optional[str]) -> Optional[str]:
        if base is None:
            return None
        if not isinstance(base, str):
            raise UserError("Base path must be a string")
        return uabspath(base)

    def _expand_paths(self, paths: List[str]) -> List[str]:
        if not paths:
            return []
        all_files: List[str] = []
        seen = set()
        for path in paths:
            if not isinstance(path, str):
                raise UserError("All paths must be strings")
            abs_path = uabspath(path)
            if os.path.basename(abs_path) in self.skip:
                continue
            if abs_path in seen:
                continue
            if not os.path.exists(abs_path):
                raise UserError("No such file or directory: %s" % abs_path)
            if os.path.isdir(abs_path):
                dir_files: List[str] = []
                for root, dirs, files in os.walk(abs_path):
                    dirs[:] = sorted([d for d in dirs if d not in self.skip])
                    files = sorted([f for f in files if f not in self.skip])
                    for name in files:
                        full_path = os.path.join(root, name)
                        if full_path in seen:
                            continue
                        seen.add(full_path)
                        dir_files.append(full_path)
                dir_files.sort()
                all_files.extend(dir_files)
            else:
                seen.add(abs_path)
                all_files.append(abs_path)
        return all_files

    def _key_for_path(self, path: str, base: Optional[str]) -> str:
        if not base:
            return path
        try:
            common = os.path.commonpath([path, base])
        except ValueError:
            raise UserError("File '%s' is outside base path '%s'" % (path, base))
        if common != base:
            raise UserError("File '%s' is outside base path '%s'" % (path, base))
        return os.path.relpath(path, base)

    def _scan_file(self, path: str) -> Dict[str, object]:
        try:
            st = os.stat(path)
        except OSError as e:
            raise UserError("Failed to stat '%s': %s" % (path, e))
        try:
            checksum = checksum_file(path, ["md5"])[0]
        except Exception as e:
            raise UserError("Failed to checksum '%s': %s" % (path, e))

        return {
            "md5": checksum,
            "size": st.st_size,
            "mtime": st.st_mtime,
            "ctime": st.st_ctime,
            "atime": st.st_atime,
        }

    def scan(self, relative_to: Optional[str] = None) -> Dict[str, Dict[str, object]]:
        """Perform the scan and return a mapping of path -> file info."""
        base = self._normalize_base(relative_to) or self.relative_to
        if self.threads == 1:
            keyed_results = dict(
                (self._key_for_path(path, base), self._scan_file(path))
                for path in self._files
            )
        else:
            tmp_results: Dict[str, Dict[str, object]] = {}
            with ThreadPoolExecutor(max_workers=self.threads) as executor:
                futures = dict((executor.submit(self._scan_file, path), path) for path in self._files)
                for future in as_completed(futures):
                    path = futures[future]
                    tmp_results[path] = future.result()
            keyed_results = dict(
                (self._key_for_path(path, base), tmp_results[path])
                for path in self._files
            )

        self._results = keyed_results
        return dict(keyed_results)

    def get_files(self) -> List[str]:
        """Return the list of absolute file paths that will be scanned."""
        return list(self._files)

    def get_results(self) -> Dict[str, Dict[str, object]]:
        """Return the results from the last scan (empty until scan() has run)."""
        return dict(self._results)
