# Introduction #

So, you think Boar is a useful tool, but you are reluctant to trust it with your most important data? Maybe you are working for a company that for legal reasons needs to be able to prove that your document archive is intact. In this article I'll describe how you can verify the contents of a boar repository in a manner that does not require you to trust boar.

Note that this information is somewhat intended for persons with some experience with programming. Much of the idea behind an external verification tool is that it is a relatively small program that you can read and convince yourself that it performs as expected. If you cannot read code, you have no choice but to trust the software as it is. There may still be some valid reasons for running external verification though, such as making sure a truncated repository still contains everything you want to keep.

# The problem #

As a careful data hoarder and Boar user, you do of course run the "verify" command on your repository from time to time, at the very least when updating your clones. Now, what happens when you do that? Well, as Boar goes through the procedures, it prints many lines of reassuring progress information, hopefully a lot of happy "OK":s.

However, consider if Boar is lying to you? It could be unintentional, perhaps a bug that causes some type of errors to not be detected. Or it could be intentional, just to make Boar look advanced. For an example of the latter, take a look at these [clever counterfeit USB drives](http://blog.jitbit.com/2011/04/chinese-magic-drive.html). When you plug it in, it looks like a 500 GB drive, but in reality it contains only a tiny flash drive. When you save files to the drive, they are simply thrown away, but the drive saves the correct file names and file sizes, so everything looks OK. If you actually try to read the file, you only get trash back.

Now, as the author of Boar, I know what Boar is doing, and I'm quite confident that any type of problem with the repository would be detected. But how can I convince you of that? If you are a software developer (with a lot of time), you could inspect my code and my tests and convince yourself that everything is provisioned for, but it is a lot of work.

So, what to do? How can you use Boar for critical data while at the same time not trusting Boar?

# External verification - what does it mean? #

The key to not having to trust boar, is to create some type of information that is enough to identify a correct set of data, and then store that information somewhere outside of Boar. Since boar didn't create that information, nor did it store it, there is no risk of Boar lying to you. You can then use that trusted information to verify your data.

To be more concrete, such a piece of information could be a simple checksum file. First, create a checksum of all your data using any algorithm you prefer, then put the checksum file on a usb stick or in the Cloud. Write a simple tool that pulls out the files one by one from Boar and verifies that the checksums match.

In fact, you could check in the checksum file itself into the Boar repository. As long as you know what the trusted checksum of your checksum file is, that is all you need.

# Using the packaged EVT #

Boar comes with a tool that can be used to get a very high level of confidence. Of course, you need to trust the tool itself, but it is simple enough to inspect, or even write your own.

In your Boar source tree, there is a folder named "evt" which stands for "external verification tool". This tool uses md5-checksums and md5sum-style manifest files. If you choose to implement your own tool, you can of course use any checksum algorithm you desire (but you still need to store the md5 checksum as well, as your evt must use that when asking Boar for the contents of the file).

## Creating the manifest ##

So, let's say you want to import all your pictures from your once-in-a-lifetime cruise to Antarctica. You insert the memory card into your computer, but since you are highly paranoid, the first thing you do is not to run Boar, but to create a md5 manifest file. There are many tools available to do this, but eventually you'll have a file named "manifest.md5" that looks like this:
<pre>
2f9ee7e7ce80de8d7b526c227e067404 *DCIM/100CANON/IMG_0001.JPG<br>
d41d8cd98f00b204e9800998ecf8427e *DCIM/100CANON/IMG_0002.JPG<br>
3f4dc6c01892f5d224faa7bcf956a80a *DCIM/100CANON/IMG_0003.JPG<br>
... and so on<br>
</pre>

We'll check in the manifest together with the pictures later. Now, calculate the md5 checksum of the manifest file itself.
<pre>
5e0a13049b13c7296853a0bb2562dec2 *manifest.md5<br>
</pre>

This checksum-of-checksums is the signature of your entire set of data. It is this you will use to verify the contents of your repository, so this signature must **not** be stored in Boar. Instead, write it down on a piece of paper and put somewhere safe.

## Importing into Boar ##

Now you are ready to start up Boar. How you organize your folders is up to you, but I like to keep the camera data as untouched as possible for imports, and have the manifest on the top level. So, let's say you have completed the import and your session looks like this:
<pre>
MyPictures/Antarctica/manifest.md5<br>
MyPictures/Antarctica/DCIM/100CANON/IMG_0001.JPG<br>
MyPictures/Antarctica/DCIM/100CANON/IMG_0002.JPG<br>
MyPictures/Antarctica/DCIM/100CANON/IMG_0003.JPG<br>
... and so on<br>
</pre>

And the signature of the manifest file, "5e0a13049b13c7296853a0bb2562dec2", that we calculated above, is safely stored on paper.

## Using the EVT and manifest to verify your data ##

Now, you have imported all your pictures into Boar, and Boar claims that it all went well. It is time to make sure it speaks the truth.
<pre>
verify-manifests.py /home/me/BOARREPO -B 5e0a13049b13c7296853a0bb2562dec2<br>
</pre>

First this tool will fetch and verify the manifest contents by using the given signature. Boar uses md5 checksums as file identifiers, so the evt can conveniently use the signature of the checksum file to both retrieve the manifest contents and to verify the integrity.

verify-manifests.py now knows that it has an intact manifest file, and now it needs to verify the contents of every file in the manifest. It uses the known expected md5sum for every file to retrieve the actual file contents, and then calculates the actual checksum and compares it with the expected checksum.

If all the files passes this test, the external verification has succeeded and Boar did indeed tell the truth!

Since we trust verify-manifests.py (or your own implementation of the same), we are now confident that all imported files actually are stored in the repository and can be retrieved by using their checksum. And by using the manifest and the repository contents, we can easily restore the file tree as specified in the manifest, if need be.

However, note that the provided verify-manifests.py script does not perform any specific checks on the structure or contents of the file tree in the latest snapshot. The external verification tool only guarantees that **all your data is still there** (but it may be buried in the version history).
