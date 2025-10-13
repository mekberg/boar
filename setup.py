import importlib
import importlib.util
import subprocess
import sys


def _load_setuptools():
    if importlib.util.find_spec("setuptools") is None:
        ensurepip_spec = importlib.util.find_spec("ensurepip")
        if ensurepip_spec is not None:
            ensurepip = importlib.import_module("ensurepip")
            try:
                ensurepip.bootstrap()
            except Exception:
                pass
        try:
            subprocess.check_call(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "--upgrade",
                    "pip",
                    "setuptools",
                    "wheel",
                ]
            )
        except Exception as exc:  # pragma: no cover - fatal during packaging
            raise ModuleNotFoundError(
                "setuptools is required but could not be installed automatically"
            ) from exc
    return importlib.import_module("setuptools")


setup = _load_setuptools().setup

import py2exe

setup(console=['boar'])
