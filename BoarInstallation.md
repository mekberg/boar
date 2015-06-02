# Windows #

## Using the Windows installer ##
The easiest way to get started with Boar is to use the provided Windows installer. It will install Boar and set up the system PATH accordingly. After installation, you should be able to start a command prompt and type "boar.exe" and get a nice help message.

## Using the multi-platform package ##
If you for some reason cannot use the automatic windows installer, this section describes the manual way to install Boar on Windows.

First, you need to install a recent version of python. [Python 2.6](http://www.python.org/ftp/python/2.6.6/python-2.6.6.msi) should work fine. (Skip Python 3.0 and later for now).

Unpack the boar archive somewhere. I like to put it in the python installation directory, "C:\python26\boar".

To avoid having to type the full path to boar every time, add the boar path to the system path list. Please be careful, or you might break something.

  1. Right-click My Computer, and then click Properties.
  1. Click the Advanced tab.
  1. Click Environment variables.
  1. Click to select the PATH variable
  1. Click Edit to change its value.

The value is a semicolon-separated list of paths. Add the path where you placed boar to the end of it. It should look something like this when you are done:

`PATH=c:\windows\system32;c:\windows;c:\python26\boar`

Finally, edit the file "boar.bat" in the boar directory. Make sure the path to the python installation directory is correct for your installation.

You should now be able to open a command prompt and type "boar" and get a nice help message.

If it doesn't work, look at the CommonProblems page.

# Mac OS X #

Although boar should in principle run wherever there is a python interpreter, you may run into issues with boar on mac. To begin with, you will need a somewhat modern python with the right libraries. That is, 2.6 or higher (but not 3.0). The one coming with your system is likely too old, so check out http://www.python.org/getit/mac/.

After that, I really have no idea, since I don't own a mac. But I guess it should be similiar to the Linux installation outlined below.

If you have successfully installed and used boar on a mac, feel free to send me an email describing what you had to do, and I'll update this page.

# Linux #
1. Unpack the boar archive:

> `tar xzf boar.15-Feb-2012.tar.gz`

2. As root, put the boar directory somewhere on your system where it is accessible by everyone, for instance /usr/local.

> `mv boar /usr/local`

3. Make sure that all the files are readable by all users:
> `chmod -R a+r /usr/local/boar`

4. Create a symbolic link to the boar executable in /usr/bin:
> `ln -s /usr/local/boar/boar /usr/bin/boar`