### When I try to run boar, I get this error: "ImportError: No module named bsddb" ###

This problem used to occur on some Python builds on OSX and Windows. Later versions of Boar does not use bsddb. Upgrade your Boar installation to fix this problem.

### I have just imported a lot of data / checked out a huge directory, and any boar command I try to run in the workdir takes forever! ###

The first time you access a newly created workdir (by import or checkout), boar will again read every file and calculate the checksums. The good news is that this will happen only the first time you access the new workdir, after that the checksums will be cached. This is a safety procedure, to compensate for the (unlikely) chance that there was a read/write failure during the import or checkout. By re-calculating the checksums, any spurious errors will be detected.