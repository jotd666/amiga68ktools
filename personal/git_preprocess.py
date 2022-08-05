import os,re,glob,shutil,subprocess



for usrdir in glob.glob(r"K:\jff\AmigaHD\PROJETS\HDInstall\DONE\*\*\usr"):
    def report(msg):
        print("{}: {}".format(usrdir,msg))
    sourcedir = os.path.join(usrdir,"source")
    if os.path.isdir(sourcedir):
        asm = os.path.join(usrdir,os.pardir,"*HD.asm")
        g = glob.glob(asm)
        if g:
            for s in g:
                os.rename(s,os.path.splitext(s)[0]+".s")
        wm = os.path.join(usrdir,os.pardir,"Makefile_windows.mak")
        if os.path.exists(wm) and os.path.getsize(wm):
            wmd = os.path.join(sourcedir,"Makefile_windows.mak")
            if os.path.exists(wmd):
                # check git
                #p = subprocess.run(["git","status","."],cwd=usrdir,stdin=subprocess.DEVNULL,capture_output=True)
                #print(p.stdout.decode())
                #p = subprocess.run(["git","add","."],cwd=usrdir)
                p = subprocess.run(["git","ls-files","-o","."],cwd=sourcedir,stdin=subprocess.DEVNULL,capture_output=True)
                untracked = p.stdout.decode().strip()
                if untracked:
                    uf = untracked.split()
                    for u in uf:
                        print(sourcedir,"====>",u)
                        if u.endswith(".s"):
                            subprocess.run(["git","add",u],cwd=sourcedir,stdin=subprocess.DEVNULL)
                        elif u.endswith("HD.asm"):
                            asmname = os.path.join(sourcedir,u)
                            sname = os.path.join(sourcedir,u.replace("HD.asm","HD.s"))
                            if os.path.exists(sname) and sname != asmname:
                                os.remove(asmname)
                            else:
                                os.rename(asmname,sname)
            else:
                shutil.copy(wm,wmd)
                report("makefile.mak not in usr/source")
    else:
        srcdir = os.path.join(usrdir,"src")
        if os.path.isdir(srcdir):
            report("renamed src to source")
            os.rename(srcdir,sourcedir)
        else:
            report("no source dir")