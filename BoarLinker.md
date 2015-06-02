## Introduction ##

BoarLinker is an external Windows tool written by Krzysztof Suszka. It creates NTFS links from a local Boar blob storage so that you get a directory tree that looks exactly as it would look if you performed a regular checkout. The only difference is that all the files are write protected, take up no disk space, and the "checkout" itself takes almost no time.

## Safety ##

Although BoarLinker makes this operation as safe as possible, it is important to understand that there are some risks. The linked files will point to the actual contents of the boar blobs. If you were to modify the contents of a linked file, the blob would change as well, and Boar will then consider the whole repository corrupt. To prevent you from accidentally doing this, BoarLinker sets the links and the blobs read-only at creation. Still, you are only a click or two away from making the file writable and potentially wrecking your repository.


BoarLinker can be downloaded at https://bitbucket.org/ksuszka/boarlinker