# Introduction #

Boar normally retains all your data forever and makes it just about  impossible for any data to change or disappear undetected. If you are  saving your photos for eternity, that is exactly what you want, and you  should stop reading here.

However, there may be other situations and usage scenarios where you need  to purge obsolete data. If you need to do that, "truncate" is the only  command that permanently removes data from a repository.

# What does truncate do #

Truncate will remove all the previous snapshots and their blobs from a  specific session. The session will then contain only whatever was in the  last snapshot of the session at the time "truncate" was invoked. The  deleted data will be gone forever (well, at least after you have emptied  the trash, see below).

It is not yet possible to only remove selected snapshots, it's all or  nothing.

# Enabling truncate #

The truncate command must be enabled for a specific repository before it  can be used. This is a a safety precaution to make sure that you cannot  activate "truncate" by accident. To enable truncate, you must manually  create an empty file named "ENABLE\_PERMANENT\_ERASE" (note: no three-letter  suffix) in the top directory in the repository. Without this file,  "truncate" will not function (nor will any of the lower level functions  supporting the operation).

Example: If your repository is located at "/home/jdoe/repo", you would enable truncate by running the command:

> `touch /home/jdoe/repo/ENABLE_PERMANENT_ERASE`

# Running truncate #

The syntax of truncate is simply:

> `boar truncate <Session name>`

# Taking out the trash #

All the deleted session data, and all the deleted blobs, are moved to the  tmp/ directory in the repository. They are placed in directories with the  prefix `"TRASH_"` and a random suffix. You need to delete these directories  manually if you want to free up space and delete the data permanently.
There is no easy way to automatically push the ejected data back into the  repository if you should change your mind. But at least it is  theoretically possible until you delete them permanently. Perhaps you  should consider burning them to a DVD or something just in case. But  again, if you are that paranoid you should not use "truncate" in the first  place.

# Truncate and clones #

The "truncate" operation will replicate to clones when using the "clone"  command. That is, the same data will be deleted in the clone as on the  master. The "ENABLE\_PERMANENT\_ERASE" file must be created manually in each  clone before cloning, or cloning will fail.

# Questions and answers #
## Is this safe? ##

This feature is reasonably well tested. As other Boar operations, it can  be safely aborted and resumed. Still, if you chose to activate and use  this feature in your Boar repository, you are making a compromise with  data safety. Even if Boar was blessed with divine perfection, "truncate"  still makes it possible to lose data if misused. Be careful.

## I have truncated my session, but I can still see all the deleted  snapshots in the sessions directory? ##

The entries are still there, but the contents have changed. The only  information that remain from the original snapshot is the session name and  the snapshot fingerprint. This is necessary to implement truncation cloning in a safe way.

## How do I create the ENABLE\_PERMANENT\_ERASE file in windows? ##

This simple task is ridiculously complicated in Windows if you are hiding file suffixes, which is the default setting. The easiest way in that case is to open a dos prompt and enter the command:

> `echo. >C:\MY_REPO_PATH\ENABLE_PERMANENT_ERASE`

If you can see file suffixes, just right click, select "New -> Text Document". Rename the file to ENABLE\_PERMANENT\_ERASE without any suffix, and answer "yes" when windows asks you if you want to change the suffix. Then move the file to the repository root.