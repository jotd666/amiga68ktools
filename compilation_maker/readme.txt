Compilation Maker: a new tool to create Amiga games compilations

Here's a quick dox I gathered from my posts at EAB (http://eab.abime.net/showthread.php?p=1196545#post1196545)

What's new you're going to ask? Well, this tool does all the job:

- it scans the games directory for whdload slaves
- it analyses and extracts the info (game name / copyright) from whdload slave
- it creates startup scripts
- it creates startup sequence and inserts all needed files to boot AGS from an empty disk
- it tries to find a matching game screenshot from my personal database (delivered with the tool)
- it's currently able to produce menus with images for whdload & cd32load & cd32load (IDEHD mode)

All 3 modes have been tested and work.
No copyright infringement since all copyrighted data (kickstart ROMs) must be provided by the user.
no manual intervention is needed, that's the cool point.

AGA is required (because it uses an AGS AGA layout)

tool is command line but currently distributed as GUI, running on Windows (source available in "src", command line version should be easily adaptable to other platforms)

The tool cannot create HDF files (I'm interested if someone has some python script to do that), it just takes a "GAMES" (or other) root dir (or multi-root dir), and scans for slaves in it.
It computes the ID of the games from the slaves, and creates AGS menus from all the slaves at the same level.

Ex: if you have C:\foo\bar\MY_HD\GAMES, it creates startup seq, all required dirs in C:\foo\bar\MY_HD. So when you start winuae you just select this dir, make it "bootable", and it works.

If you want it to work on a real miggy, then mount this partition, your system & your amiga HD drive in Winuae and copy all the files to your fresh amiga HD (CD32load HD mode needs FFS only, WHDload mode can use any format, PFS..)

Special CD32Load mode features looking up game name in a built-in database to set the proper joypad/keys mapping (can be a lot of work to do manually).
It also tries to find a relevant image in the internal IFF image base. There's a good % of success on known games.

It can also take a kickstarts directory as input, to copy on the DEVS/Kickstarts dir of the target.

Extra tools developped with other EAB members allow to create an ISO image. 
That's not built-in in the tool for now but that will be done if enough need it. 

How to use:

ATM, just run the tool, select a directory containing a GAMES/DEMO directory (there's a HDROOT_DEMO directory provided for example), choose your launcher and click "run"

The directory will be updated with everything to boot the HD folder. Test in WinUAE, copy on a real amiga HDD/CD (burning a bootable CD32 is a little trickier, we're working on that)

The database features are still very alpha (on GUI) so just leave them as-is (only needed for CD32load ATM)
They're used when creating CD32load compilations.
If a game is not in the database, it will have default controller mappings / possibly needs expert settings to run properly.
So those games are logged in the "missing DB" csv file for you to complete the options (or do nothing if OK)
and copy the line into the existing database csv file.

If you update a lot of lines, I'd appreciate if you send me a copy of your updates so I can deliver a better database next time.

History:

1.2: 10/12/2017

- handle spaces in directory names
- fixed non-working cleanup for .ags files

1.1: 29/11/2017
- fixed slave name retrieval from whdload slaves
- changed database 2nd column from "tested" to "alternate game name"

1.0: 15/11/2017
- first release
