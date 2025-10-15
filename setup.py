try:
    from setuptools import setup
except ImportError:  # pragma: no cover - fallback for legacy Python installs
    try:
        from distutils.core import setup  # type: ignore[attr-defined]
    except ImportError as exc:  # Python 3.12+ without setuptools present
        raise SystemExit("setuptools is required to build Boar") from exc

import py2exe

setup(console=['boar'])
