import os,csv,glob,re,sys,csv,shutil,time
import find,fnmatch,filecmp

import whdload_slave
import json

preview = False

def secs2date(s):
    return time.strftime("%Y-%m-%d %H-%M-%S",time.localtime(s))

if True:
    projects = r"K:\jff\AmigaHD\PROJETS"
    source_dir = os.path.join(projects,r"HDInstall\DONE")

    f = find.Find()
    slave_list = f.init(source_dir,pattern_list=["*.slave"])
    for slave in slave_list:
        if "usr" in slave.split(os.sep):
            usr_slave = slave
            dev_slave = os.path.join(os.path.dirname(os.path.dirname(slave)),os.path.basename(slave))
            if os.path.exists(dev_slave):
                if filecmp.cmp(usr_slave,dev_slave,shallow=False):
                    # same file avoid
                    pass
                else:
                    print("updating usr slave with dev slave: {}".format(dev_slave))
                    shutil.copyfile(dev_slave,usr_slave)