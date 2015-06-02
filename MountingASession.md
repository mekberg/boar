**Note for Windows users**: this page describes a Linux-only feature. For a similar functionality on Windows, try BoarLinker instead.

# Introduction #

If you are using Linux, you can use boar to mount a session, allowing you to browse and read the files without having to check them out first. You will need to have [FUSE](http://fuse.sourceforge.net/) installed in your system. If you have a recent distribution, it's quite likely already installed.

# Commands #

First, create an empty directory to use as a mount target. The directory will look like it contains all your files.

  * $ mkdir /home/joe/mountdir

To mount the session "MyPictures" from the repository /home/joe/boar\_repo to the folder you just created:

  * $ boarmount /home/joe/boar\_repo MyPictures /home/joe/mountdir

Done! Now you can look around in mountdir and read files. You cannot change anything, all files are read-only. (If you need to change a file, you still need to check it out in the usual way)

When you are tired of looking at your files, use the FUSE tool "fusermount" to unmount your session:

  * $ fusermount -u /home/joe/mountdir