try:
    from setuptools import setup
except ModuleNotFoundError:
    import ensurepip
    import importlib

    ensurepip.bootstrap()
    setup = importlib.import_module("setuptools").setup

import py2exe

setup(console=['boar'])
