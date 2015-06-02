# Introduction #

This page describes how to run a Boar server on Windows. The setup process is a bit more complicated than on other platforms, but the result is a fast and stable Boar server. Boar uses the third-party wininetd package to install Boar as a Windows service that can be managed as any other native service.

# Security implications #
Before you continue reading this page, note that Boar provides no authentication mechanisms. Anyone who has access to your network, will have full read/write access to your Boar repository. Specifically, you should **never** expose a Boar stand-alone server directly to the Internet.

However, if you have a safe and protected LAN, with trusted clients that needs to access the same repository, and you prioritize ease-of-use and speed, this page is for you. Using a stand-alone Boar server makes it possible to use your network to its full potential.

# Setup #

## 1. Install Boar ##

This page assumes you are using the Boar windows installer, which provides boar.exe and does not require any other dependencies. See BoarInstallation for details on how to install Boar on Windows.

## 2. Start an administrator command prompt ##

To start a command prompt with administrative privileges, right-click "Start->Accessories->Command Prompt" and select "run as administrator".

All commands on this page must be executed at the administrator command prompt.

## 3. Create a wininetd configuration ##

Create a config file for wininetd named "c:\windows\wininetd.conf". An easy way to do this is to type "notepad c:\windows\wininetd.conf" at the admin command prompt.

The config file should look like this, but you need to change username:password to the values of the user that will own the server process. Also make sure the path to boar.exe is correct, as well as the path to the repository to serve.
```
10001 username:password "C:\Program Files (x86)\Boar\boar.exe" serve -S "C:\Users\UserName\REPO_TO_SERVE"
```

## 4. Install wininetd ##
  * Go to http://xmailserver.org/wininetd.html and download wininetd (link at the bottom of the page).

  * Unpack wininetd to "C:\Program Files (x86)" (or wherever you prefer to install it).

  * Cd to the Release folder in the wininetd package that you unpacked earlier, like "C:\Program Files (x86)\wininetd-0.7\Release"

  * Run the command `wininetd --install`

  * To make wininetd and your boar server start automatically every time your computer reboots, run this command (note the space after the equals sign):
> > `sc config wininetd start= auto`

  * To start wininetd after installation, reboot your computer. (Or run the command `net start wininetd`)

## 5. Success! ##

You should now be able to run this command on your server and get a listing of contents of the repository:


> `boar --repo=boar://localhost:10001/ ls`

## 6. Open up the firewall ##

For your boar server to be reachable from your Home/Work network, you need to allow it access through the windows firewall. Be sure that you understand the implications of opening up your firewall! You should never allow public access to your Boar server, as it has no authentication mechanisms at all. Anyone who can access your network will have full read/write access to your repository.

  * Open "Control panel -> System and Security -> Windows Firewall -> Allow a program through Windows Firewall"
  * Click "Change settings"
  * Click "Allow another program"
  * Click "Browse"
  * Select "C:\Program Files (x86)\wininetd-0.7\Release\wininetd.exe" and click "Open"
  * Click "Add"
  * Locate "wininetd" in the listing of "Allowed programs and features".
  * Ensure that the "Home/Work" checkbox is checked, and that the "Public" checkbox is clear (note that this is the opposite of the default setting).
  * Click "OK"


## 7. Troubleshooting ##
  * You can read the log output from wininetd by using the usual Windows service monitoring facilities (the "Event Viewer" and "Services").

  * If the wininetd service starts, then stops, make sure the config file is named correctly. Especially, make sure that you haven't accidentially named it "wininetd.conf.txt", as might easily happen if you create the file with notepad without specifying the filename on the command line.