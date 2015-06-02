**Table of contents**


# Introduction #

There are many situations where it is necessary or useful to connect to a repository over a network. Boar supports using ssh for establishing secure and authenticated communication channels with a Boar repository.  The server needs to be running Linux for the procedure described below to work.

For other ways to set up a Boar server, see [BoarServer](BoarServer.md).

# Boar+SSH setup for Windows #

On windows, Boar will use plink.exe for connecting to the server. Plink is a part of the excellent [putty](http://www.chiark.greenend.org.uk/~sgtatham/putty/) suite of programs. You can download plink.exe individually, but you should get the full [Putty windows installer](http://the.earth.li/~sgtatham/putty/latest/x86/putty-0.62-installer.exe), as it contains the tools that you need to set up automatic authentication.

Setting up automatic authentication is a one time task. There are several good tutorials available on how to do this, for instance this one: [Public Key Authentication With PuTTY](http://www.ualberta.ca/CNS/RESEARCH/LinuxClusters/pka-putty.html).

You must make sure that the authentication does not require entering any password. This means that you must use [Pageant](http://the.earth.li/~sgtatham/putty/0.62/htmldoc/Chapter9.html#pageant), which also comes in the putty package. You could also choose to simply leave the password field empty when you create your private key. Of course, for security reasons, this is inadvisable, no matter how convenient and time saving it might be...

You should now have an entry in the Putty session list with the computer hosting your repository, we'll call it "myserver" from now on.

To test your setup, start a command prompt and enter:

> `plink.exe myserver "echo Hello world"`

If everything works, you should NOT have to enter any password, the  response should be "Hello world" which means you are all set to go!


# Boar+SSH setup for Linux #

You must set up ssh so that you can log in to the server without having to enter any password. There are many tutorials available for this, this one is concise and to the point: [SSH login without password](http://www.linuxproblem.org/art_9.html).

_If_ you choose to protect your private key with a password, you will need to use ssh-agent to avoid having ssh prompt you (and thereby confusing Boar). This is a good page on how to use ssh-agent: [Passwordless SSH logins](http://www.cs.utah.edu/~bigler/code/sshkeys.html).

To test your setup, enter this command (substituting "username" and "myserver.com" with your own):

> `ssh username@myserver.com "echo Hello world"`

If everything works, you should not be prompted for a password, and the response should be "Hello world".

# Using a remote Boar repository #

To connect to a remote repository, you use a specially formed repository reference.

> `boar+ssh://[<username>@]<myserver.com>/path/to/repo`

For example, if your server is named "myserver.com", your server username is "jdoe" and your repository in located in /home/jdoe/REPO, you could list the contents by entering this command:

> `boar --repo=boar+ssh://jdoe@myserver.com/home/jdoe/REPO ls`

The username part is optional if you have defined it in your Putty session on windows or in the .ssh/config file on Linux.

You can now work with your repository as usual by using the boar+ssh:// repository reference wherever you would otherwise give a local file system path to a repository.

# Troubleshooting #

## I get a "Connection closed by other side" message ##

  * Make sure that both client and server are using the same version of boar. Later versions will tell you if there is a version mismatch, but the first release will not.
  * Is the path set up correctly on the server? You should be able to log on to the server and type "boar" and get a help message.
  * Is the path set up correctly for non-interactive shells? If boar works fine on the server, but you get "command not found" when you execute `ssh user@myserver.com boar`, then this is likely your problem. If you are using bash, the user .bash\_profile file is only used for interactive shells and will not be read for automatic connections. Instead, you should add the boar path in your .bashrc file.