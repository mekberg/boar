# Lean, self-contained image holding the whole Windows build toolchain for boar:
#   * Rust + the x86_64-pc-windows-gnu target + mingw-w64  -> cross-build rdedup.pyd
#   * wine64 + a full Windows CPython + PyInstaller         -> validate & freeze boar.exe
#
# Build context MUST be the repo root so the cargo dependency cache can be warmed:
#   docker build -t boar-winbuild -f winbuild/Dockerfile .
# See winbuild/README.md.

FROM debian:bookworm-slim

# Pin the Windows Python. abi3 (see rdedup/Cargo.toml) means the produced
# rdedup.pyd is not tied to this exact version, but we still need one concrete
# interpreter to link against, validate under wine, and freeze into boar.exe.
# 3.11 (not 3.12) on purpose: Python 3.12's platform module queries WMI, which
# under wine hits the unimplemented propsys.dll.VariantToString and aborts
# PyInstaller. 3.11's platform module is registry-based and works under wine.
ARG PYVER=3.11.9
ARG PYSHORT=311

ENV DEBIAN_FRONTEND=noninteractive \
    RUSTUP_HOME=/opt/rustup \
    CARGO_HOME=/opt/cargo \
    PATH=/opt/cargo/bin:$PATH \
    WINEPREFIX=/opt/wineprefix \
    WINEARCH=win64 \
    WINEDEBUG=-all \
    WINPY=/opt/winpython/tools

# --- system toolchain (kept minimal; no 32-bit wine, no recommends) ----------
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates curl xz-utils unzip file procps \
      python3-pip \
      build-essential \
      mingw-w64 mingw-w64-tools binutils-mingw-w64 \
      wine64 xvfb xauth \
 && rm -rf /var/lib/apt/lists/* \
 # The wine64 package ships only /usr/lib/wine/wine64 (the launcher lives in the
 # separate `wine` package, which would drag in 32-bit). Symlink it onto PATH.
 && ln -sf /usr/lib/wine/wine64 /usr/local/bin/wine64 \
 && ln -sf /usr/lib/wine/wine64 /usr/local/bin/wine

# --- Rust + Windows GNU cross target -----------------------------------------
# Pin 1.77.2 (not stable): Rust >= 1.78's std seeds its RNG via ProcessPrng from
# bcryptprimitives.dll, which wine < 9.0 does not provide, so the cross-built
# rdedup.pyd fails to load under wine. 1.77's std uses RtlGenRandom (advapi32),
# which both wine and real Windows have. The shipped module is unaffected.
ARG RUST_VERSION=1.77.2
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
      | sh -s -- -y --profile minimal --default-toolchain ${RUST_VERSION} \
 && rustup target add x86_64-pc-windows-gnu \
 && rm -rf /opt/cargo/registry/cache

# --- full Windows CPython via the nuget package ------------------------------
# The nuget layout (under tools/) ships python.exe with an unzipped stdlib,
# libs/ (MSVC import libs) and python3.dll/pythonNNN.dll. That makes it both
# PyInstaller-friendly and a source for the stable-ABI import lib below.
RUN curl -sSL -o /tmp/py.nupkg "https://www.nuget.org/api/v2/package/python/${PYVER}" \
 && mkdir -p /opt/winpython \
 && unzip -q /tmp/py.nupkg -d /opt/winpython \
 && rm /tmp/py.nupkg \
 && test -f "${WINPY}/python.exe" || (echo "nuget python layout unexpected" && ls -R /opt/winpython | head && false)

# --- mingw-compatible import lib for the stable ABI (python3.dll) -------------
# rustc's gnu target links with ld, which cannot consume the MSVC python3.lib,
# so synthesise a GNU import lib from the stable-ABI forwarder DLL.
RUN cd /tmp \
 && cp "${WINPY}/python3.dll" . \
 && gendef python3.dll \
 && x86_64-w64-mingw32-dlltool --dllname python3.dll --def python3.def --output-lib libpython3.a \
 && cp libpython3.a "${WINPY}/libs/" \
 && rm -f /tmp/python3.dll /tmp/python3.def /tmp/libpython3.a

# --- initialise the wine prefix --------------------------------------------
RUN xvfb-run -a wine64 wineboot --init >/dev/null 2>&1 ; sleep 2 ; true
# Stop wine from launching its interactive crash debugger on an unimplemented
# Windows API call: without this, a stray crash hangs the build forever waiting
# on winedbg. With it, the offending process just exits and we move on.
RUN xvfb-run -a wine64 wine64 reg add 'HKCU\Software\Wine\WineDbg' \
      /v ShowCrashDialog /t REG_DWORD /d 0 /f >/dev/null 2>&1 ; true

# --- install PyInstaller into the Windows CPython ---------------------------
# Running pip *under wine* crashes on unimplemented APIs, so instead resolve the
# Windows wheels with the host's pip and unzip them into the Windows interpreter's
# site-packages. PyInstaller's only native piece is its bootloader, which ships
# prebuilt in the win_amd64 wheel.
#
# pywin32-ctypes and pefile are listed explicitly: pip evaluates their
# `sys_platform == 'win32'` markers against this *Linux* host and would otherwise
# drop them, but PyInstaller hard-requires pywin32-ctypes on Windows.
RUN python3 -m pip download --only-binary=:all: \
      --platform win_amd64 --python-version ${PYSHORT} --implementation cp --abi none \
      --dest /tmp/wheels pyinstaller setuptools pywin32-ctypes pefile \
 && for w in /tmp/wheels/*.whl; do unzip -o -q "$w" -d "${WINPY}/Lib/site-packages"; done \
 && rm -rf /tmp/wheels \
 # setuptools' distutils-precedence.pth runs _distutils_hack at every startup;
 # drop it to keep interpreter startup minimal and predictable under wine.
 && rm -f "${WINPY}/Lib/site-packages/distutils-precedence.pth" \
 && xvfb-run -a wine64 "${WINPY}/python.exe" -c "import PyInstaller, sys; print('PyInstaller', PyInstaller.__version__, 'on', sys.version.split()[0])"

# --- warm the cargo dependency cache (download + offline-capable runs) --------
# Copy just the crate manifest/sources so `cargo fetch` can resolve and cache
# pyo3/rusqlite without baking a (large) compiled target dir into the image.
COPY rdedup /opt/rdedup-src
RUN cargo fetch --manifest-path /opt/rdedup-src/Cargo.toml || true

COPY winbuild/build.sh /usr/local/bin/build.sh
RUN chmod +x /usr/local/bin/build.sh

WORKDIR /src
ENTRYPOINT ["/usr/local/bin/build.sh"]
