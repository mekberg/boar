

# Introduction #

By default, Boar recognizes identical files and stores them only once, this is a simple case of "file level deduplication" (FLD). However, what if you change only a small part of a large file? With only FLD, a modified file would be considered a completely new and unique file that would be stored in its entirety. However, with block level deduplication (BLD), modifications will be recognized as such, and only the actual changes will be added to the repository, potentially (see below) saving a lot of space. Contrary to some other block level deduplication systems, Boar allows for deduplication even for data that is non-aligned.

The BLD feature is provided by a C extension that must be compiled on the machine where it is intended to be used.

# Should you use this feature? #

This is a feature that you should not use unless you are sure that you will benefit from it. Keeping track of all data in the repository adds  overhead. If your data is unsuitable for deduplication, you will pay a price in lost performance without any benefits.

Perhaps most important, if you use deduplication, Boar no longer use a constant amount of RAM. Instead, RAM use will increase with the size of the repository (see section on hardware requirements). This effectively puts a practical limit on the repository size.

# What kind of data can be deduplicated? #

A typical case where Boar BLD works very well is when modifying the header information on large files, such as jpeg or mp3. Lots of space saved if you do this kind of operations often.

It also works quite well on files that are uncompressed compositions of individual data blocks, such as databases, disk images or firmwares. Results may vary depending on the exact characteristics of the changes. Typically, larger, continuous changes are better.

It works very badly on data that has been compressed or otherwise processed so that it no longer looks like the original, such as .zip files or re-compressed video. These kinds of files will commit as any other file, but you will not see any storage benefits.

# Maturity #

The deduplication feature in Boar is under development and should be considered beta software.

# Requirements #

## OS ##
Currently, the deduplication module can only be installed on Boar servers running on Linux. The clients can however run on any OS normally supported by Boar.

## Hardware ##

Deduplication is a demanding task and the more CPU power you have the better. A somewhat modern desktop/server 64-bit CPU is recommended. That will get you at least 20 MB/s in commit speed. Specifically, it is not recommended to run deduplication on any kind of low-powered ARM or VIA CPUs, such as you might find in a NAS appliance. (But if you do, please mail me and tell me what performance you got)

Deduplication requires a lot of RAM during commits. The exact required amount may change somewhat as the feature matures, but the required amount always scales linearly with the physical size of the repository on disk. A 100 GB repository will require about 1 GB of RAM. A 1 TB repository will require about 10 GB of RAM.

# Installation #

The deduplication module can currently only be built and installed on Linux. The module is only needed by the server, there is no need to install the module for clients.

To build and install the module, execute this command line in the Boar top directory (the directory containing the cdedup folder):

> `gmake -C cdedup && cp cdedup/cdedup.so .`

Verify that the installation was successful by executing

> `boar --version`

There should be a line in the output saying "Deduplication module v1.0". If the module did not install correctly, there will instead be a line "Deduplication module not installed".

# Usage #

## Creating a new deduplicated repo ##
To create a new BLD repository, use the -d flag to "mkrepo". Example:

> `boar mkrepo -d my_deduplicated_repo`

That is all that is needed. Everything added to this repository will be deduplicated.

If you do not give the "-d" flag, an ordinary, non-deduplicated repository will be created.

## Deduplicating an existing repo ##

It is not possible to convert an existing repository to a BLD repository in-place, but you can create a deduplicated clone of your repository by following these steps:

Create a new empty deduplicated repository:

> `boar mkrepo -d MyDeduplicatedRepo`

Then, clone your repository to this newly created repo:

> `boar clone MyRepo MyDeduplicatedRepo`

You now have a deduplicated clone containing everything in your original repo, but hopefully saving a lot of space. After making sure that the operation completed successfully, and verified the contents of the clone, you may delete the original repository.

## How much space did I save? ##

To view various numbers and statistics about your repository, use the "stats" command

> `boar stats`

The interesting numbers regarding deduplication is "virtual size" and "actual\_size". The virtual size is the sum of all unique committed files. The actual size is the sum of all file data in your repository. For a non-deduplicated repository, these numbers will be the same. For a deduplicated repository, the actual size will hopefully be smaller than the virtual size.