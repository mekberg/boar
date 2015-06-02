# Installation #

Please see BoarInstallation for details on installation. Also make sure you are subscribed to the [Boar mailing list](https://groups.google.com/forum/?fromgroups#!forum/boarvcs), it is a low-volume list and it is the only way you will know if there are any important bugs or security issues found in Boar.

# Quickstart #
First of all, you need to create a repository somewhere. This is where all your stuff will end up, so make sure it’s a safe location.

> `boar mkrepo /home/joe/boar_repo`

You must then create a session before you can add any data. A session is a logical division of the repository. It is only for helping you organize your stuff, so choose a name that reflects what you are going to store there. It is not currently possible to rename sessions, so choose carefully.

> `boar --repo=/home/joe/boar_repo mksession MyPictures`

A new session named “MyPictures” will be created.

Now you are ready to import your stuff. Assume you have folder called “pictures”. This is how you import it and make it into a work directory.

> `boar --repo=/home/joe/boar_repo import pictures MyPictures`

Your data will be checked in and Boar will turn the "pictures" folder into a work directory by writing some configuration files in it. Now that you have a work dir, you will not need to use the --repo option when you are working in that directory.

Now, if you make some changes to the work dir (adding, deleting, modifying files), you can see what changes you have made by making sure you are standing in the work directory and typing:

> `boar status`

To commit any changes, simply type:

> `boar ci`

To update a work dir with changes that has been checked in from somewhere else, type:

> `boar update`

If you want to check out your session somewhere else, just type

> `boar --repo=/home/joe/boar_repo co MyPictures`

And finally, to ensure that all your precious data is intact:

> `boar --repo=/home/joe/boar_repo verify`

# That was fun! What now? #

This covers the basics. Check out the CommandReference. Especially the commands "locate" (will help you clean up that old HDD of yours), and "clone" (a safe and fast way to backup your repository).