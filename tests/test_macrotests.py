"""
Pytest wrapper to run the legacy shell-based macro tests quietly.

This executes the same scripts that macrotests/macrotest.sh runs, but
integrates them into pytest so you get standard reporting and -q silence.

Usage:
  pytest -q tests/test_macrotests.py

Environment variables respected (same as the shell runner):
  - BOAR_TEST_REMOTE_REPO: 0 (local), 1 (simulated remote), 2 (ssh)
  - BOAR_HIDE_PROGRESS: set to 1 to suppress CLI progress
  - BOAR_SERVER_CLI: path to boar entrypoint used by tests
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest


MACRO_DIR = Path(__file__).resolve().parent.parent / "macrotests"


def list_shell_tests():
    for p in sorted(MACRO_DIR.glob("test_*.sh")):
        # Exclude archived or data files inadvertently matching pattern
        if p.name.endswith(".sh"):
            yield p


@pytest.mark.parametrize("testcase", list(list_shell_tests()), ids=lambda p: p.name)
def test_macro_shell(testcase: Path, monkeypatch: pytest.MonkeyPatch):
    # Mirror the environment setup from macrotests/macrotest.sh
    macro_dir = MACRO_DIR
    boar_top = macro_dir.parent

    # Unset REPO_PATH to avoid damaging real repos
    monkeypatch.delenv("REPO_PATH", raising=False)

    boar = str(boar_top / "boar")
    boarmount = str(boar_top / "boarmount")
    monkeypatch.setenv("BOAR", boar)
    monkeypatch.setenv("BOARMOUNT", boarmount)
    monkeypatch.setenv("BOARTESTHOME", str(macro_dir))
    monkeypatch.setenv("BOAR_SERVER_CLI", boar)

    # Determine Python interpreter from boar shebang like the shell scripts do
    try:
        with open(boar, "rb") as f:
            first = f.readline().decode("utf-8", "ignore")
    except FileNotFoundError:
        first = ""
    pybin = first.split(" ", 1)[-1].strip() if first.startswith("#!") else ""
    if not pybin or not shutil.which(pybin):
        # Fallbacks similar to run_tests_nodedup.sh
        pybin = shutil.which("python3") or shutil.which("python") or pybin
    if pybin:
        monkeypatch.setenv("PYTHON_BINARY", pybin)

    # Ensure PATH contains macro test dir (some tests call helper scripts in CWD)
    monkeypatch.setenv("PATH", f"{macro_dir}:{os.environ.get('PATH','')}")

    # Quiet progress by default
    monkeypatch.setenv("BOAR_HIDE_PROGRESS", "1")

    # Create isolated temp working directory and cache
    tmpdir = tempfile.mkdtemp(prefix=f"boar-{testcase.stem}-", dir="/tmp")
    monkeypatch.setenv("BOAR_CACHEDIR", os.path.join(tmpdir, "cache"))

    try:
        # Run the test, capturing output; pytest will display it only on failure
        proc = subprocess.run(
            ["bash", str(testcase)],
            cwd=tmpdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=os.environ.copy(),
            timeout=600,
            check=False,
        )
        if proc.returncode != 0:
            # Attach output to the assertion for visibility on failure
            pytest.fail(
                f"Macro test {testcase.name} failed with code {proc.returncode}\n\n" + proc.stdout
            )
    finally:
        # Clean up on success; on failure pytest.fail has already raised
        shutil.rmtree(tmpdir, ignore_errors=True)
