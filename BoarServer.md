# Introduction #

Before you continue reading this page, note that the safest way to access a Boar repository over a network is to use the method described in [BoarOverSsh](BoarOverSsh.md). That method requires no running processes on your server, neither does it open any ports. All connections are authenticated and encrypted by ssh. That said, not all situations are created equal. If you have a safe and protected LAN, with trusted clients that needs to access the same repository, and you prioritize ease-of-use and speed, this page is for you. Using a stand-alone Boar server makes it possible to use your network to its full potential.

# Linux - using xinetd #

**Warning: a xinetd server using this procedure will be open for reading and writing for anyone who can access the given network host and port.**

On Linux, there are many advantages to using the xinetd service to publish your Boar repository. The service automatically starts when your machine does, any error messages is passed to the usual system logs and the server is generally very robust.

First, make sure that the xinetd package is installed on your system. Then, create a file named `/etc/xinetd.d/boar` with the following content:

```
service boarserver
{
        disable                 = no
        port                    = 10001
        socket_type             = stream
        protocol                = tcp
        wait                    = no
        user                    = <USER NAME>
        passenv                 = PATH
        server                  = /usr/bin/boar
        env                     =
        server_args             = serve -S <REPO PATH>
        type                    = UNLISTED
#       bind                    = 127.0.0.1
}
```

Change `<REPO PATH>` and `<USER NAME>` to your own suitable values. `<REPO PATH>` must be an existing local repository. `<USER NAME>` is the user that will own the server process. Make sure that user has read/write access to the repository path. Modify the other values as necessary. If you uncomment the "bind" parameter, the server will only be accessible from the same machine.

Restart xinetd with `"sudo service xinetd restart"` and access the repository using the URL `boar://<hostname>:<port>/`


# Linux - using boar serve #

**Warning: a boar server using this procedure will be open for reading and writing for anyone who can access the given network host and port.**

If you want to quickly and easily publish a boar repository without requiring any system modifications, this is the method for your. Simply run the command `"boar serve <REPO PATH>"` where `<REPO PATH>` is the local path to the repository. Boar will start serving the repository on the default port (10001). You can change port and interface to bind to using the -p and -h parameters. The command does not exit and will not print any further information. You can shut down the server by pressing ctrl-c.

# Windows #

Please see BoarServerOnWindows.