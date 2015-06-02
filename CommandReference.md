# Command reference #

This is a list of all commands that can be issued to boar. Note that this list refers to the latest development version of boar, there may be minor differences compared to the latest release.



## --version ##
Syntax: `boar --version`

Prints some information about boar, including the version id.

## cat ##
Syntax: `boar cat [-r|--revision <revision>] [-B|--blob <blob id>] [--punycode] <session name></path/...> ...`

Output one or more files directly to stdout. The output from this command is guaranteed to only contain the file data.

If --revision is given, that version of the file will be outputted.

If --blob is given, the blob with the given id will be outputted (no session path necessary when using --blob)

If --punycode is given, the session path will be assumed to be encoded in [punycode](http://en.wikipedia.org/wiki/Punycode). This is primarily useful when scripting commands on platforms with flaky unicode support.

## ci ##
Syntax: `boar ci [-m "log message"] [-a|--add-only] [-e|--allow-empty] [-q|--quiet]`

Commits any changes that has occured in the workdir, thereby creating a new snapshot.

You can use the "-m" flag to add an optional log message. (The log message must be specified on the command line. There will be no attempt to start an text editor if the message is missing.)

If the --add-only (also "-a") option is given, only new files are committed. Modified and deleted files are ignored. This may be useful for instance if you are using your camera memory card as a boar workdir, and want to keep images in the session even though you have deleted them on the camera to free up space.

If the --allow-empty option is given, a new snapshot will always be committed, even if there are no changes to commit.

If the --quiet option is given, less progress information is printed.

## clone ##
Syntax: `boar clone [-r|--replicate] [--skip-verification] <source repository> <destination repository>`

Creates or updates a copy of the source repository. This is a safe and fast way to create a copy of the repository. Boar makes sure that the two repositories are consistent (the destination repository, if it already exists, must be a earlier revision of the source repository). The cloning process can be safely aborted at any time, and it is resumeable.

**The clone command is intended only for making and maintaining backups of your repository. If you modify the clone, it is no longer considered a clone and cannot be updated from the master. There is no way to merge changes between repositories.**

If the --replicate flag is given, boar will continuously monitor and sync any incoming changes, making sure the clone stays updated. When this option is used, boar will never exit (until it is killed or an error occurs).

If --skip-verification is given, no verifications will be performed on the repositories before cloning. This makes cloning much faster, but is potentially dangerous as corruption on the master might spread to the slave undetected.


## co ##
Syntax: `boar co [-r <snapshot id>] <session name[/path/]> [workdir]`

Checks out a session (or subdir of a session) as a new workdir. If no workdir path is specified, the name of the session will be used.

Normally the latest snapshot is checked out, but you can use the -r option to specify an older snapshot.

## diffrepo ##
Syntax: `boar diffrepo <repository 1> <repository 2>`

Checks if the two given repositories are identical and then prints a message and sets the return code. Return code 0 means they are identical, anything else means they are not. This command is probably most useful for scripting.


## getprop ##
Syntax: `boar getprop <session name> <property name> [-f <filename>]`

Get a session property. The value of the session property will be printed. If the -f argument and a filename is given, the value of the property will be written to the given file instead.

## info ##
Syntax: `boar info`

Prints some information about the current work dir.

## import ##
Syntax: `boar import [-e|--allow-empty] [--ignore-errors] [-W|--no-workdir] [-n|--dry-run] [-v|--verbose] [-m "log message"] <directory> <session name[/path/]>`

Import the given directory into the given session, optionally to a specific sub path in the session. By default boar will turn the imported directory into a workdir, but you can disable this behavior with "--no-workdir".

The “--dry-run” option performs a dry run. That is, nothing will actually be added to the repository, but you will be able to see what would have happened.

The “--verbose” option enables verbose mode, meaning some information and progress will be printed.

The "-m" flag is used to add an optional log message. (The log message must be specified on the command line. There will be no attempt to start an text editor if the message is missing.)

If the --allow-empty option is given, a new snapshot will always be committed, even if there are no files to commit.

The --ignore-errors option can be given if any unreadable files should be skipped, instead of aborting the operation.

Import will never replace any existing files in the session. If you try, you will get an error message.

## list ##
Syntax: `boar list [-m] [session name [snapshot id]]`

With no arguments, lists all sessions in the repository. If session name is given, lists all snapshots in that session. If a snapshot id is given as well, a list of all files in that snapshot is printed.

Meta sessions (sessions containing properties for other sessions) are normally hidden. By giving the -m argument, these sessions are shown.

_If you just want to browse the contents of a repository, the "ls" command is a friendlier alternative._

## locate ##
Syntax: `boar locate <session name> [file/dir] [file/dir] [...]`

Will scan the given files or directories and show what files are present in the given session, and if so, where in the session. This is useful to figure out if some files are already present in your repository.

## log ##

Syntax: `boar log [-v|--verbose] [-r|--revision <revision range>] [<session name></path/...> | <workdir path>]`

Show log messages and timestamps for a file or tree. This command can be used both in workdirs on individual files, or on session paths in repositories.

If --verbose is given, a list of what files has changed in each revision will be printed.

If --revision is given, only the log entries for these revisions will be shown. Revision can be given as a single integer, or as a range on the form N:M.


## ls ##
Syntax: `boar ls [-v|--verbose] [-r|--revision <revision>] [session name/path/...]`

With no arguments, lists all sessions in the repository. If a session name with an optional path is given, lists the contents of the specified directory.

By default "ls" lists the contents of the latest available revision, but earlier revisions can be specified with the "-r" option.

If the "-v" verbose flag is given, file size data is printed after every file name.

## mkrepo ##
Syntax: `boar mkrepo <repository path>`

Create a new repository.

## mksession ##
Syntax: `boar mksession <session name>`

Create a new session in a repository.

## setprop ##
Syntax: `boar setprop <session name> <property name> [-f <filename> | <property value>]`

Set a session property. Typical use is to set an [ignore list](IgnoreAndInclude.md) for a session. The new value of the property can be specified as the last argument, or the new value can be read from a file, specified with the -f argument.

## status ##
Syntax: `boar status [-v]`

Prints any changes that has been done to the workdir (that is, what will be checked in if “boar ci” is executed). “-v” will print status information about all files, even unchanged ones.

Two status letters will be printed for each file. The leftmost column is as follows:

  * A - The file is new
  * D - The file has been deleted
  * M - The file has been modified
  * i - The file is ignored by boar for some reason (special files, soft links)

## truncate ##
Syntax: `boar truncate <session name>`

The truncate command will permanently erase all old revisions of a specific session. Due to the nature of the command, it must be enabled on a per-repository basis. For more information about truncation, and how to enable the command, see [Truncate](Truncate.md).

## update ##
Syntax: `boar update [-r <revision>] [--ignore-errors] [-c|--ignore-changes] [-q|--quiet]`

Updates the workdir with any changes from the repository. If an revision is specified with the -r argument, the workdir will be updated to that revision. Otherwise, it will be updated to the latest revision. Note that "update" can be used to update to an earlier revision as well.

Modified files in the workdir will never be changed by an update. If you want to revert some changes to a file, just delete the modified file and execute "update" again.

Normally, the update process will stop with an error message if some files cannot be updated (if they are locked by another process, for instance). The --ignore-errors option makes boar just print a warning and continue with the update. Please note that boar will not remember that those files were not updated. Hence, the next time you check in, boar will commit the old version of those files.

If --ignore-changes is given, the workdir revision will be updated, but no incoming changes will be applied. This can be used to revert a session to an earlier state, by first running "update -r <desired revision to revert to>" and then "update --ignore-changes" followed by a normal commit.

## verify ##
Syntax: `boar verify [--quick]`

Verifies that the repository is healthy.

If the --quick command is given, verification of the blobs is skipped. You should normally not use --quick, since it will not detect corrupt files. It will however detect things like if some of the files are missing or if the meta data files has been corrupted.

# Experimental/debugging commands #

## find ##
Syntax: `boar find <hex md5sum> <session name>`

Given a md5 checksum, prints a list of files in the current session that has that checksum.