# winbuild — a single Windows `boar.exe` (with the Rust `rdedup` backend)

This directory builds a self-contained `boar.exe` for 64-bit Windows, with the
Rust deduplication port (`rdedup`) compiled in and active. Everything happens
inside one Docker image, so the host stays clean and the build is reproducible
on any machine with Docker.

## What it does

A single Docker image carries the whole Windows toolchain:

* **Rust + `x86_64-pc-windows-gnu` + mingw-w64** — cross-compiles a genuine
  Windows `rdedup.pyd` on Linux (no Windows machine needed). The module is built
  against CPython's **stable ABI** (`abi3`, see `../rdedup/Cargo.toml`), so one
  `.pyd` works regardless of the exact Python version.
* **wine64 + a full Windows CPython + PyInstaller** — imports and tests the
  cross-built `.pyd` in a Windows-like environment, then freezes `boar` plus all
  its modules and the `.pyd` into one `--onefile` `boar.exe`.

The container `ENTRYPOINT` (`build.sh`) runs the four-step pipeline:
cross-compile → validate under wine → freeze → smoke-test.

## Usage

Run from the **repo root** (the build context must be the repo root so the
image can warm the cargo dependency cache):

```sh
# 1. Build the toolchain image (once; ~minutes, a few GB).
docker build -t boar-winbuild -f winbuild/Dockerfile .

# 2. Run the pipeline. Mount the repo read-only and an output dir with space.
mkdir -p /gigant/boarwin/out
docker run --rm \
    -v "$PWD":/src:ro \
    -v /gigant/boarwin/out:/out \
    boar-winbuild

# 3. Grab the result.
ls -lh /gigant/boarwin/out/dist/boar.exe
```

Copy `boar.exe` to a Windows box and run it — no Python, no Rust, no install.

### Reclaim space when done

The image is large (Rust toolchain + wine + Windows Python). Remove it with:

```sh
docker image rm boar-winbuild
```

> Output artifacts go to the bind-mounted `/out` (here `/gigant/boarwin/out`),
> **not** into the image, specifically so the image can be deleted freely and so
> nothing lands on the small root filesystem.

## Files

| File             | Purpose                                                              |
|------------------|---------------------------------------------------------------------|
| `Dockerfile`     | The lean all-in-one Windows toolchain image.                        |
| `build.sh`       | In-container pipeline: cross-compile → validate → freeze → smoke-test. |
| `boar_entry.py`  | PyInstaller entry shim; runs the `boar` script and defaults the backend to `rdedup`. |
| `boar.spec`      | PyInstaller `--onefile` spec (hidden imports + the bundled `.pyd`). |

## Notes & tuning

* **Python version** — pinned to 3.11.9 via the `PYVER`/`PYSHORT` build args.
  Not 3.12: Python 3.12's `platform` module queries WMI, which under wine hits
  the unimplemented `propsys.dll.VariantToString` and aborts PyInstaller. Override
  with `docker build --build-arg PYVER=3.10.11 --build-arg PYSHORT=310 ...` if
  needed. abi3 means the produced `rdedup.pyd` still runs on any CPython ≥ 3.8 on
  the target Windows box.
* **Rust version** — pinned to 1.77.2 via the `RUST_VERSION` build arg. Rust ≥
  1.78's std seeds its RNG via `ProcessPrng` from `bcryptprimitives.dll`, which
  wine < 9.0 lacks, so the cross-built `.pyd` would not load under this wine.
  1.77 uses `RtlGenRandom` (advapi32), present on both wine and Windows.
* **Deduplication** — the bundled `rdedup.pyd` is the dedup backend (exposed to
  boar under the historical name `cdedup` via the `cdedup.py` shim). Set
  `BOAR_DISABLE_DEDUP=1` to force the pure-Python fallback.
* **Output ownership** — the container runs as root (wine needs a writable prefix),
  so files under `/out` are root-owned; `sudo chown -R "$USER" /gigant/boarwin/out`
  if you need to manage them as your user.
* **Disk** — the Docker image (~5 GB: Rust toolchain + wine + Windows Python) lives
  on the default Docker root. Keep build artifacts on a roomy mount (the `/out`
  bind) and `docker image rm` afterwards.
