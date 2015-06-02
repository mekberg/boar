

# Introduction #

This document will describe the boar source code from a high level perspective. The goal is to make it a little bit easier for developers to get started with the Boar code base. This is **not** the place to start if you simply want to use Boar (for that, go to [Quickstart](Quickstart.md)).

# Boar structure #

Boar is roughly divided into two parts: a front end and a back end. The front end is the client side with command line parser and workdir handling, and the back end is the repository / server side.

## Front end ##
The front end includes these files:

| **Filename** | **Purpose**|
|:-------------|:-----------|
|boar          |The command line tool. Parses the given options and performs the desired operations.|
|boar.bat      |A help script to make boar executable on Windows|
|client.py     | Code for connecting to a local boar repo or a boar network server|
|workdir.py    |Handles anything involving the local file system, normal checkins/checkouts, imports, and so on.|
|treecomp.py   |Code for comparing file trees and finding out what has changed.|

## Back end ##

The back end is the part that actually writes to the repository.

| **Filename** | **Purpose**|
|:-------------|:-----------|
|front.py      |This is the repository "front" or interface towards the client. Because this interface should be easy to implement over a network protocol, all method calls must pass and return only primitive values.|
|jsonrpc.py    | Boar network protocol. Based on json-rpc but heavily modified. |
|boarserve.py  | Code for running a Boar network server|
|blobrepo/repository.py|The core. Contains logic for creating, verifying, and modifying repositories.|
|blobrepo/sessions.py|Classes for creating sessions and reading data from sessions. Works intimately with repository.py |

## Common files ##

These are files that are used by both the front- and back end.

| **Filename** | **Purpose**|
|:-------------|:-----------|
|common.py     |Lots of useful functions and classes that are not specific to the Boar project.|
|common\_boar.py|Useful functions and classes that are specific to the Boar project.|
|boar\_exceptions.py|Exceptions defined and used by Boar|


## Tests ##

Unit tests and command line tests.

| **Filename** | **Purpose**|
|:-------------|:-----------|
| tests/test\_workdir.py | Tests operations on the Workdir class |
| blobrepo/tests/test\_repository.py | Tests operations on the Repository and SessionReader/SessionWriter classes |
|run\_tests.sh | unix script that executes all existing tests, both macro tests and unit tests.|
|macrotests/   | This directory contains everything related to testing the Boar command line executable on unix.|
|macrotests/macrotest.sh| A number of successive tests for the Boar command line tool. |
|macrotests/test_`*`.sh_| Tests for the command line client |
|macrotests/test\_regression_`*`.sh_| Tests that old repository formats are still handled ok. |
|macrotests/test\_issue`*`.sh| Regression tests for specific issues (see the [bug tracker](https://code.google.com/p/boar/issues/list) for details on each issue) |

# Reading the code #

## Terminology ##

This table explains some terms you may come upon in the code. All terms should ideally only have a single meaning, but unfortunately, there are some legacy uses of some terms that may confuse a reader.

| **Word** | **Meaning** |
|:---------|:------------|
| session  | The word session means a series of successive snapshots with a common session\_name. Sometimes unfortunately used as a synonym to "snapshot". |
| session\_id, revision, revision\_id, snapshot, snapshot\_id, | All of these will indicate the id number of a snapshot (the numbers found under sessions/ in the repo) |
|blob      |A file stripped of its name, identified by their 128-bit md5 checksum expressed as a hexadecimal string. Stored under blobs/ in the repository |
|bloblist  |The list of filenames mapped to blobs making up a snapshot.|
|front     |The back end of Boar (the "front" of the back-end... maybe not the best name) |

# Writing the code #

## Keeping it simple? ##

Writing code that is safe and easy to understand is a difficult balancing act. But I have tried to follow these rules:

  * Minimize inheritance. Inheritance makes it less obvious what code is being executed.
  * Avoid call-backs, event listeners and other types of "come-from" flow control.
  * Don't define and use classes unless there is a good reason. Primitives are underrated.
  * Reduce the number of user options to a minimum. Every added option makes code a little bit more complicated to test.