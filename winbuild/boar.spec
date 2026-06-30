# -*- mode: python ; coding: utf-8 -*-
# PyInstaller --onefile spec for boar.exe with the Rust rdedup backend bundled.
# Invoked under wine python:
#   wine python -m PyInstaller winbuild/boar.spec --distpath /out/dist --workpath /tmp/pyi
# See winbuild/build.sh.

import os

# PyInstaller resolves relative paths in a spec against the spec's own directory,
# not the cwd, so derive everything from SPECPATH (this file's dir = <repo>/winbuild)
# and use absolute paths. REPO is the working copy that holds boar, rdedup.pyd, etc.
REPO = os.path.dirname(SPECPATH)

hiddenimports = [
    # Native dedup backend (rdedup.pyd) plus the cdedup.py compatibility shim
    # that re-exports it under the historical name. deduplication.py imports
    # `cdedup`, which the shim resolves to rdedup; force both in.
    'rdedup', 'cdedup',
    # boar project modules. The 'boar' script is executed through runpy at
    # runtime (see boar_entry.py), so none of its imports are discovered
    # automatically; list them here and let PyInstaller pull their transitive deps.
    'blobrepo', 'blobrepo.repository', 'blobrepo.sessions', 'blobrepo.blobreader',
    'boar_exceptions', 'deduplication', 'front', 'workdir', 'common',
    'boar_common', 'boarserve', 'client', 'jsonrpc', 'treecomp',
    'statemachine', 'ordered_dict',
    # stdlib imported directly by the boar script (not reached via the modules above)
    'optparse', 'cProfile', 'pstats', 'posixpath', 'ntpath', 'errno', 'shutil',
]

a = Analysis(
    [os.path.join(SPECPATH, 'boar_entry.py')],
    pathex=[REPO],
    binaries=[
        (os.path.join(REPO, 'rdedup.pyd'), '.'),
        (os.path.join(REPO, 'python3.dll'), '.'),   # stable-ABI forwarder the .pyd links against
    ],
    datas=[
        (os.path.join(REPO, 'boar'), '.'),          # the real CLI script, run via runpy at startup
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter'],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='boar',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
)
