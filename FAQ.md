

# FAQ #

## General questions about the project ##

### **Q: So what does Boar do?** ###

**A:** Boar is a version control system for handling large binary files, something that most other VCSs doesn't handle very well. This makes it possible to version control your music, images, videos, and other valuable binary data.

It makes extensive use of checksums to make sure your versioned data is consistent at all times. The Boar repository format is very simple and well suited for long-term archival purposes, as the data can be quite easily extracted without access to the original Boar software.

You can read more about the goals of Boar in the [Rationale](Rationale.md).

### **Q: How mature is Boar?** ###

**A:** Boar is stable and ready for general usage. Features are still being added though, and usage details may change.

### **Q: What about bugs? What if boar eats my data instead of protect it?** ###

**A:** I really try to avoid that scenario, since I use boar myself to keep many years of precious memories in digital form. Boar is developed using extensive automatic testing. It is also designed so that the most critical parts, those that read/write to the repository, are compact and comprehensible and easy to audit. Boar has not yet had any bug with the potential of causing repository corruption.

### **Q: How will I know if there are any major bugs or security issues found in Boar?** ###

If you are a using Boar for anything of importance, make sure you are subscribed to the [Boar mailing list](https://groups.google.com/forum/?fromgroups#!forum/boarvcs). It is a low-volume list and any important announcements or bugs will be posted to that list only.

### **Q: I think I found a bug** ###

Quality is of the highest importance for a tool such as Boar and bug reports are greatly appreciated. For minor problems and usability issues, please write a bug report at http://code.google.com/p/boar/issues/list For more complicated bugs or security issues, feel free to e-mail the author directly at ekberg@gmail.com.

### **Q: Is boar one of those nice, modern DVCS things?** ###

**A:** No! [DVCS](http://en.wikipedia.org/wiki/Distributed_revision_control) are wonderful for code, but when you have huge amounts of data, you want to have as few copies as possible. In a DVCS you create a local copy of the "main" repository, which can be of significant size for the amounts of data that boar was designed for. Boar uses a traditional central repository model, and when you check out a folder you only get 1 copy on your disk. This is a feature.

### **Q: But I saw a "clone" command in the reference. Are you sure boar isn't one of those nice, modern DVCS things?** ###

**A:** The boar "clone" command does indeed create (or update) a full copy of another repository. There is however no corresponding "push" command to merge changes from one repository to another. The boar "clone" command is therefore only useful as an administrative tool to create and maintain backups of the main repository.

### **Q: How does boar compare with git?** ###

[Git](http://git-scm.com/) is excellent for code, but it is not constructed to handle huge binaries. Linus himself has said that "The git architecture simply sucks for big objects"[\*](http://kerneltrap.org/mailarchive/git/2006/2/8/200591). There are several problems, but the most obvious ones are that git will require at least as much RAM as the largest file you are handling, which may be a lot if you are handling video files. The git model with a repository in every workdir is not practical when the size of the repository might be close to the size of the drive it is on. Also, git comes with a lot of complexity caused by the need for code merging and patching. Binaries can usually not be merged in a meaningful way, and boar does not attempt to do it and is therefore in some ways simpler.

### **Q: How does boar compare with rdiff-backup?** ###

**A:** There is certainly a lot of overlap in functionality with [rdiff-backup](http://www.nongnu.org/rdiff-backup/). Both stores revisions of potentially large file trees, both makes it possible to verify integrity, both has a transparent storage format. There is a philosophical difference in that boar intends to be the primary storage of your files, not a backup.

Some important practical differences:

  * Boar uses a VCS-style workflow with check out, update, commit. You can check out only part of a large tree and work with that separately.
  * Boar can be used for coordinating work. You can commit your changes and update to receive changes from other.
  * Boar protects all stored pathnames from being mangled by the local file system. A boar repository can for instance be moved between Windows / UNIX file systems without any problems. You may have problems with rdiff-backup if your copy is on another type of file system.

### **Q: I'm running Mac OS X. Will Boar work for me?** ###

**A:** Boar is tested on Linux and Windows, but people are indeed running Boar on OS X too. Some unique mac features, like resource forks, will probably not work, but for storing regular files, it should work fine. However, as it is not routinely tested on that platform, consider yourself a beta tester if you decide to use Boar on OS X. Take a look at BoarInstallation for some details on getting Boar to run on OS X.

### **Q: When will feature X be completed?** ###

**A:** Sorry, I will not make the common mistake to try to give time estimates in what is essentially a spare time project. They would be wrong anyway. As of 2015, I'm actively working on boar, which means that features will drop in every now and then. However, my general recommendation is that you should only use boar if you can live with what is in there right now.

### **Q: How are Boar releases numbered?** ###

Boar does not use numbered releases like "2.0" or similar. Every release is simply tagged with the date it was published.

### **Q: Why the name "Boar"?** ###

**A:** It is a nice, pronounceable and short word that works well at the command line. Boars are large and robust animals that eat a lot and are not very picky, which are all good qualities in a binary vcs. If you want an acronym, it could be "Big Object ARchive". Also, all other names were taken.

## Usage ##

### **Q: Will Boar notice if my repository is damaged by bad sectors or other sources of silent data corruption?** ###

**A:** Yes! This is a large part of the why Boar was created in the first place. All checked in files are stored with its corresponding checksum. All the meta data in the repository is verified by checksums. Every snapshot has a checksum that is a function of all the included files and their data. Even the checksums have checksums (so that you will know if the file or the checksum is corrupted). If anything unexpectedly changes in your repository, you will know it.

### **Q: What exactly is a "session" and why do I need to create one?** ###

**A:** You can think of a session simply as a top directory in the repository. You need at least one session to be able to use boar (due to how boar stores your stuff internally). For most purposes, one session is all you need.

Internally, boar keeps data from different sessions separate. Some features, like including or excluding files based on filename (see IgnoreAndInclude) are configured per session. It is also possible to purge older revisions of specific sessions. Also, operations on huge sessions containing lots of files will by necessity take more time, but sessions containing fewer files will not be affected.

Reasons to use more than one session would be
  * If there is a natural partitioning for your data and you want to optimize your repository for speed.
  * If you expect to at some point want to purge old revisions of some  data, but not other data.

### **Q: What if my repository becomes corrupted? Can Boar fix it?** ###

**A:** No! While Boar excels at _detecting_ problems, it can not fix any errors found. It is up to you to keep clones of the repository so that you simply can throw out the main repository if it becomes corrupt. Of course, Boar makes it easy to create and maintain clones. You can even have Boar continuously replicate all changes to a clone. Read about the "clone" command in the CommandReference for details.

### **Q: What if I cancel an import or check-in in progress? Will my repository become corrupt?** ###

**A:** No. All operations that modify the repository are atomic. That is, they will either complete successfully or leave the repository unchanged. It is completely safe to kill boar at any point. The tmp dir in the repository may become cluttered after a while though, see [issue 31](http://code.google.com/p/boar/issues/detail?id=31).

### **Q: What limits does boar have regarding file and tree sizes?** ###

**A:** There are no practical limits for file sizes. You can check in files of any size in boar. RAM usage does _not_ increase when handling large files. There are no limits on the number of files imposed by boar, but the file list is loaded into RAM when accessed, and is therefore limited by the amount of RAM + virtual memory in your machine. In practice, that should allow for millions of files on a modern machine.

You should also know that boar is affected by the repository host file system. For instance, if you are using FAT32, the largest allowed individual file size is 4 GB. This may change in the future, see [issue 29](http://code.google.com/p/boar/issues/detail?id=29) for details.

### **Q: How does boar handle conflicts?** ###

**A:** A conflict occurs when someone else has checked in a new revision of a file that you have modified in your work directory. Boar will not attempt to merge the changes, as boar does not have any knowledge of specific file formats. You will be told that the file has been modified on the server when you perform an update, but it will not be changed. If you check in the file, it will simply replace the latest revision as usual.

### **Q: I'm thinking of using boar on my home directory / system files / whole drive. Would that work?** ###

**A:** That is probably not a good idea. Boar does not try to preserve file attributes, such as ownership and permission bits. Also, empty directories, soft links and special files like device nodes are simply ignored. Boar might become better at those things eventually, but for now it is tailored for ordinary data files.

### **Q: If I move files around, or create copies of files, will boar store the changes efficiently?** ###

**A:** Yes. Identical files will only be stored in the repository once, no matter how you rename or move them around, or in which session they reside.

### **Q: If I make a small change to the contents of a huge file, will boar store the change efficiently?** ###

**A:** Yes, Boar provides very efficient block-level deduplication feature, but it must be explicitly enabled. At the time of writing it is only available for Linux on the development branch. See UsingDeduplication for details.

Out of the box however, Boar does not attempt to store changes to files as deltas. A new or modified file will be stored in its entirety.

### **Q: I have have just imported/checked out a huge directory, and now I've run a commit/status/update command, and it takes forever!** ###

**A:** Don't throw boar away just yet. Boar needs to verify that the stuff in your workdir actually is what it should be. This will take some time, but it only happens once per workdir.

### **Q: Can I connect to a boar repository over a network?** ###

**A:** Yes. You can host Boar servers on Windows or Linux. See [BoarOverSsh](BoarOverSsh.md) and [BoarServer](BoarServer.md) for more information.

### **Q: Can I make boar ignore certain files?** ###

**A:** Yes. Check out the IgnoreAndInclude feature.

### **Q: Is it safe to use boar with multiple users sharing a single repository?** ###

**A:** Yes. Boar is designed for this situation.

### **Q: Is it safe to use boar with multiple users sharing a single work directory?** ###

**A:** No! It will not harm the repository, but unintended consequences are likely. Don't do that.