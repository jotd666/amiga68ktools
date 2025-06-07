import os,shutil,sys

program_dir = os.path.dirname(__file__ if not hasattr(sys,"frozen") else os.path.dirname(__file__))

ags2_source = os.path.join(program_dir, "data", "AGS2_Install")
c_source = os.path.join(program_dir,"data","c")
libs_source = os.path.join(program_dir,"data","libs")


def doit(destination_directory,kickstarts_dir=None,ags_subdir="AGS",master_quitkey=None):
    if not os.path.isdir(destination_directory):
        os.mkdir(destination_directory)

    def mkdir(d):
        d = os.path.join(destination_directory,d)
        if not os.path.isdir(d):
            os.mkdir(d)

    mkdir("s")
    mkdir("c")
    mkdir(ags_subdir)
    for i in os.listdir(c_source):
        tgt = os.path.join(destination_directory,"c",i)
        try:
            os.chmod(tgt,0o777)
        except OSError:
            pass
        shutil.copy(os.path.join(c_source,i),tgt)
    dest_lib = os.path.join(destination_directory,"libs")
    if os.path.isdir(dest_lib):
        shutil.rmtree(dest_lib)

    shutil.copytree(libs_source,dest_lib)

    for i in ["AGS2","AGS2.conf","AGS2Helper","orig_AGS2Menu",
    "AGAWide-Background.iff","AGAWide-Empty.iff","README.txt"]:
        shutil.copy(os.path.join(ags2_source, i), os.path.join(destination_directory, ags_subdir))
    # copy with direct ok name too
    shutil.copy(os.path.join(ags2_source, "orig_AGS2Menu"), os.path.join(destination_directory, ags_subdir,"AGS2Menu"))
    mkdir("devs")
    if kickstarts_dir:
        mkdir("devs/kickstarts")
        src_rtb_dir = os.path.join(program_dir, "data", "devs", "kickstarts")
        dest_kick_dir = os.path.join(destination_directory,"devs","kickstarts")
        for i in os.listdir(src_rtb_dir):
            shutil.copy(os.path.join(src_rtb_dir,i),dest_kick_dir)

        if kickstarts_dir != dest_kick_dir:
            for i in os.listdir(kickstarts_dir):
                # only copy file if it has a .RTB
                if os.path.isfile(os.path.join(dest_kick_dir,i+".RTB")):
                    shutil.copy(os.path.join(kickstarts_dir,i),dest_kick_dir)

    mkdir(ags_subdir)
    startup_seq = """C:freeanim >NIL:
C:setpatch >NIL:
C:Assign T: RAM:
C:Assign AGS: SYS:{}
{}C:Anticlick
devs:monitor/PAL
devs:monitor/NTSC
AGS:AGS2
""".format(ags_subdir,"C:Assign ENV: RAM:\nsetenv QUITKEY {}\n".format(master_quitkey) if master_quitkey else "").encode("latin-1")
    with open(os.path.join(destination_directory,"s","startup-sequence"),"wb") as f:
        f.write(startup_seq)

if __name__=="__main__":
    doit(sys.argv[1])