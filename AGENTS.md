# Boar codebase overview

This repository contains Boar, a snapshotting backup/version control tool aimed at safely storing large directory trees. The project is largely written in Python with a few shell utilities and an optional C extension for block deduplication. The notes below summarize the layout of the tree and highlight the major components so you can navigate and extend the code confidently.

## Core layout

- boar – The main command line interface. It wires together repository access, the RPC client, deduplication helpers, progress reporting, and command implementations for operations such as ci, clone, list, and verify. The CLI depends heavily on the helpers defined in boar_common.py, common.py, front.py, and blobrepo/.
- boarserve.py – Implements the RPC server used for boar+tcp/boar+ssh transports. It spins up JSON-RPC handlers backed by the Front API and is designed to work both over stdio (for SSH) and TCP sockets.
- client.py – Connection factory for remote repositories. It parses Boar URLs, establishes transports (local, TCP, SSH), and returns Front objects that the CLI can operate on.
- front.py – Defines the repository façade/API that all higher-level code interacts with. It exposes session management, clone/update logic, file retrieval helpers, and progress-aware cloning utilities. Use this instead of touching repository internals directly.
- workdir.py – Handles workdir synchronization: scanning the filesystem, building manifests, comparing to repository state, and preparing commit metadata.
- blobrepo/ – Python package that implements the repository storage engine. Important modules include repository.py (on-disk layout, blob/session management), blobreader.py (streaming access to blob contents), and sessions.py (snapshot metadata). Unit tests for this package live under blobrepo/tests/.
- common.py & boar_common.py – Shared utility modules. common.py provides cross-cutting helpers (filesystem safety wrappers, hashing, JSON helpers, logging, concurrency primitives) while boar_common.py contains Boar-specific constants, progress printing, ignore-file parsing, and validation logic. Prefer reusing utilities here instead of reimplementing them.
- boar_exceptions.py – Centralized definition of the exception hierarchy used across the CLI, RPC layer, and storage backend.
- deduplication.py – High-level logic for content-defined chunking and deduplication. When the optional C module is available it offloads heavy operations there; otherwise it falls back to pure Python implementations.
- jsonrpc.py – Embedded JSON-RPC implementation adapted for Boar. Both client and server code import this to send commands over pipes or sockets.
- boarmount – FUSE-based helper that mounts a repository snapshot as a read-only filesystem. It relies on front.py and blobrepo.repository to enumerate files and serve blob data on demand.
- treecomp.py, statemachine.py, ordered_dict.py, manifest – Supporting utilities used for manifest generation, set comparisons, deterministic orderings, and other CLI features.

## Native code and packaging

- cdedup/ – Optional C/Cython implementation of the deduplication primitives (blocksdb, rolling checksum, etc.). The Makefile and setup-cython.py build the module into cdedup.so, which the Python code detects at runtime. Keep the Python fallbacks working for environments where the extension is unavailable.
- innosetup/ – Windows installer scripts and resources.

## Tests and tooling

- tests/ – Python unit tests targeting the high-level CLI, workdir scanning, and common utilities.
- blobrepo/tests/ – Unit tests specifically for the repository storage layer.
- macrotests/ – Shell-based integration tests that exercise full workflows (clone, commit, regression scenarios). macrotests/macrotest.sh orchestrates the suite and can be run in local, simulated remote, or SSH modes via environment variables.
- perftests/ – Performance benchmarks (e.g., benchmark-blocksdb.py) and tree generation utilities.
- evt/ – External verification tools/scripts. Intended as a completely stand-alone base for hard core users to build their own verification framework on.
- run_tests.sh / run_tests_nodedup.sh – Convenience scripts that run all available unit tests and macro tests.

## Conventions and tips

- The project targets python 3 and later. It used to be a python 2.7 application, but has since been ported to python 3. Expect some legacy constructs and please feel free to rewrite them for modern python if that makes things easier.
- Use the helpers in common.py for filesystem access (safe_open, StrictFileWriter, create_file, etc.), hashing (md5sum, sha256sum), and JSON (get_json_module, dumps_json). Avoid calling json.load directly; most code reads data via the wrappers that enforce unicode handling and integrity checks.
- Progress indicators and user-facing messaging typically use the abstractions in boar_common.py (SimpleProgressPrinter, notice, warn) to ensure consistent formatting. Reuse them for new commands or long-running operations.
- Repository operations should go through the Front API. Directly manipulating files under blobs/ or sessions/ is reserved for the blobrepo package and its tests.
- Tests often rely on environment variables such as BOAR_CACHEDIR, BOAR_SERVER_CLI, BOAR_TEST_REMOTE_REPO, and BOAR_SKIP_DEDUP_TESTS. If you add new tests or scripts, make sure they respect the existing workflow so run_tests.sh keeps working.
- This repository intentionally keeps legacy assets (old regression archives, Windows installers, etc.) for reproducibility. Avoid deleting or moving them without updating the integration tests that reference those artifacts.

## Running tests

- The virtual environment is located in `.venv/` (not `venv/`). Always activate it before running tests: `source .venv/bin/activate`
- Macrotests must be run through `macrotests/macrotest.sh`, not directly. This script sets up required environment variables like `BOAR`, `BOAR_CACHEDIR`, and creates temporary test directories.
- To run a specific macrotest: `bash macrotests/macrotest.sh test_name.sh`
- To run all macrotests: `bash macrotests/macrotest.sh` (no arguments)
- The test harness automatically cleans up temporary directories on success but preserves them on failure for debugging (check `/tmp/boar-testname.*.log` for output)

## Command implementations

- All CLI commands are implemented as `cmd_<command>` functions in the main `boar` file (e.g., `cmd_locate`, `cmd_ci`, `cmd_clone`)
- Commands use OptionParser for argument parsing. Pay attention to the usage string and option definitions when modifying behavior
- The `globals()["suppress_finishmessage"] = True` pattern is used to suppress the "Finished in X seconds" message for commands with special output formats (like JSON)
- When adding JSON output to commands, make it opt-in via `--json` flag and ensure the output is pure JSON (no progress messages or other text)
- Use `UserError` exceptions (from boar_exceptions.py) for user-facing error messages. These are caught and displayed cleanly without stack traces

## Working with sessions

- Sessions are Boar's equivalent of branches/snapshots. Each session has multiple revisions over time
- Use `front.get_session_names(include_meta=False)` to list all sessions in a repository
- Use `front.find_last_revision(session_name)` to get the latest revision number for a session
- Use `front.get_session_bloblist(revision)` to get all blobs (files) in a specific revision
- The `invert_bloblist()` helper creates a checksum→blobinfo lookup table, useful for the locate command and similar operations

## Quick start for manual testing

If you need to manually test changes, you can set up a temporary repository and session using the following steps:

1.  **Create a repository:**
    ```bash
    ./boar mkrepo /path/to/repo
    ```

2.  **Set the repository path:**
    You can either pass `--repo /path/to/repo` to every command or set the environment variable:
    ```bash
    export REPO_PATH=/path/to/repo
    ```

3.  **Create a session:**
    Before importing data, you must create a session (branch).
    ```bash
    ./boar mksession SessionName
    ```

4.  **Import data:**
    ```bash
    ./boar import /path/to/source/dir SessionName
    ```

5.  **Checkout data:**
    ```bash
    ./boar co SessionName /path/to/workdir
    ```

Refer back to this document when navigating the code; it should help you locate the right layer for your changes and respect the project's cross-version compatibility constraints.