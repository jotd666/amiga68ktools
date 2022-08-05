import os,re,glob
import os, winshell
from win32com.client import Dispatch
desktop = winshell.desktop()

template = r"""#added by python script

PROGNAME = {}
HDBASE = K:\jff\AmigaHD
WHDBASE = $(HDBASE)\PROJETS\HDInstall\DONE
WHDLOADER = $(PROGNAME).slave
SOURCE = $(PROGNAME)HD.s
OPTS = -DDATETIME -I$(HDBASE)/amiga39_JFF_OS/include -I$(WHDBASE)\WHDLoad\Include -I$(WHDBASE) -devpac -nosym -Fhunkexe

all :  $(WHDLOADER)

$(WHDLOADER) : $(SOURCE)
	wdate.py> datetime
	vasmm68k_mot $(OPTS) -o $(WHDLOADER) $(SOURCE)

"""

build_bat = r"""@echo off
cd /D %~PD0
wmake.py
"""

run_slave = r""".key ffff

whdload {slave} preload data=WHD:{relpath}
"""

for root,dirs,files in os.walk(os.getcwd()): # r"K:\jff\AmigaHD\PROJETS\HDInstall\Aretoucher"):
    if "usr" in root.split(os.sep):
        continue

    for f in files:
        if f.endswith("HD.asm"):
            os.rename(os.path.join(root,f),os.path.join(root,f.replace(".asm",".s")))
    if "usr" in dirs:
        bs = os.path.join(root,"build.bat")
        if not os.path.exists(bs):
            with open(bs,"w") as f:
                f.write(build_bat)

        # look for user package
        gamedir_dev = os.path.basename(root)
        gamedir = re.sub("hddev","",gamedir_dev,flags=re.IGNORECASE)
        gameupperdir = gamedir[0]
        if gameupperdir.isdigit():
            gameupperdir = "0-9"

        gamefull = r"K:\jff\AmigaHD\GAMES\{}\{}".format(gameupperdir,gamedir)

        gamedir_usr = [x for x in glob.glob(gamefull+"!*") + [gamefull] if os.path.isdir(x)]
        slaves = [os.path.basename(x) for x in glob.glob(os.path.join(root,"*.slave"))]
        ecs_slave = os.path.basename(gamefull)+".slave"
        aga_slave = ecs_slave
        for s in slaves:
            if "AGA" in s:
                aga_slave = s
            elif "ECS" in s:
                ecs_slave = s

##path = os.path.join(desktop, "Media Player Classic.lnk")
##target = r"P:\Media\Media Player Classic\mplayerc.exe"
##wDir = r"P:\Media\Media Player Classic"
##icon = r"P:\Media\Media Player Classic\mplayerc.exe"


        for g in gamedir_usr:
            print(g)

            target = g
            shell = Dispatch('WScript.Shell')
            shortcut = shell.CreateShortCut(os.path.join(root,os.path.basename(g)+"_data.lnk"))
            shortcut.Targetpath = target
            shortcut.WorkingDirectory = root
            #shortcut.IconLocation = icon
            shortcut.save()

            suffix = os.path.basename(g.partition("!")[2])
            if suffix:
                runfile = "run_"+suffix
            else:
                runfile = "run"
            amigadir = "/".join(g.split(os.sep)[4:])
            if os.path.exists(os.path.join(g,"data")):
                amigadir += "/data"

            runfile = os.path.join(root,runfile.lower())
            if os.path.exists(runfile):
                pass
            else:
                with open(runfile,"wb") as f:
                    s = ecs_slave
                    if "aga" in runfile:
                        s = aga_slave

                    f.write(run_slave.format(slave=s,relpath=amigadir).encode())



        wm = os.path.join(root,"Makefile_windows.mak")
        if os.path.exists(wm) and os.path.getsize(wm):
            pass
##                with open(wm) as f:
##                    c = f.read()
##                if "added by python script" in c:
##                    os.remove(wm)
        else:
            print("missing .mak "+root)
            mc = template.format(gamedir)
            with open(wm,"w") as f:
                f.write(mc)
