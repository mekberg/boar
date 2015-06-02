

## Ignoring and including files ##

Often when you have a set of files in a directory that you are working with, there will be irrelevant files or backup files that you don't need to import into boar. Or you might have a mix of files, but you only want boar to consider one specific kind.

You can use the session properties "ignore" and "include" to control what files boar will handle.

## What happens when you ignore files? ##
If a filename matches the ignore pattern set, it will not be imported or committed. It will be invisible in the "status" command output, unless the "-v" flag is given.

If the "include" property is set, all files _not_ matching an include pattern will be ignored.

Note that if a file is first imported, and later ignored, it will _not_ be removed from the session. If a file is already present in the session, it will be handled just as if it wasn't ignored at all. That is, modifications will be committed and it will occur in "status" output.

## An "ignore" example ##

If you have a session names MySession and you want to ignore files ending with .bak and .tmp, you first create a new text file with the patterns on separate rows. The file can have any name, but I'll call it ignore.txt in this example. It must consist of a list of simple unix-style wildcard patterns (_not_ regular expressions). There must be exactly one pattern per line.

It should look like this:

```
*.bak
*.tmp
```


Then you set the "ignore" property to the contents of the file you created:
```
boar setprop MySession ignore -f ignore.txt
```

You can now delete the ignore.txt file. It serves no purpose by itself.

## An "include" example ##

If the "include" property is set, only those files matching the include pattern list will be considered. This is useful if you only want to include a certain type of files in a session.

If you only want to include images from your digital camera, you might create a pattern list such as this:

```
*.jpg
*.raw
```

Save the pattern list as a text file "include.txt" and set the session property:

```
boar setprop MySession include -f include.txt
```

## Gotchas and common problems ##

### Case sensitivity on different platforms ###
Note that the filename patterns works slightly differently on Windows and Linux. On Windows, they are case insensitive, but on Linux and other unix-like systems, they are case sensitive. This can cause unintended effects if you are working cross-platform. You can not force windows to be case sensitive, but you can make the patterns case insensitive on all platforms by simply adding both `*.jpg` and `*.JPG` to the pattern list.

### Removing unwanted prexisting files ###

If you are applying a set of ignore patterns to a pre-existing session, you will notice that already committed files are unaffected by the ignore property. You can fix this by manually deleting the unwanted files from the workdir and then commit. They will be correctly ignored from then on.

If you have a large amount of existing files to ignore, you can perform this little trick to apply the ignore patterns globally (make sure you have committed before you do this, in case something goes wrong):

  * Make sure you have an up-to-date workdir containing no changes. (i.e c:\workdir)
  * Create a new empty directory somewhere outside the workdir (i.e c:\emptydir)
  * Move all your files from your workdir to the empty folder. Do _not_ move the boar ".boar" directory, leave it in the workdir.
  * Commit your workdir - boar will think all your files have been deleted and remove them, leaving you with a blank slate.
  * Move all the files back into the workdir
  * Commit your workdir - boar will happily add back all the files, except those on the ignore list.

### Setting both the ignore and include properties ###

It is perfectly ok to set both the "ignore" and "include" properties. The ignore property will have precedence.