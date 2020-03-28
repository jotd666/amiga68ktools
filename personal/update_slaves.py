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

    dest_dirs = glob.glob(os.path.join(projects,r"CD32GAMES\[CH]DROOT_*"))

    def scan_slaves(root_dir):
        rval = dict()
        f = find.Find()
        slave_list = f.init(root_dir,pattern_list=["*.slave"])
        for slave in slave_list:
            ws = whdload_slave.WHDLoadSlave(slave)
            if ws.valid:
                key = "{} chip={} fast={}".format(ws.game_full_name,ws.basemem_size,ws.expmem_size)
                rval[key] = (slave,ws.version_string,os.path.getmtime(slave))
        return rval
        #row = [ws.game_full_name,ws.slave_info,ws.slave_copyright,hd,nr,cd,ws.basemem_size,ws.expmem_size,ws.basemem_size+ws.expmem_size,",".join(ws.flags_list),ws.kick_string,ws.kick_size,ws.slave,copycmd]


    source_slaves = scan_slaves(source_dir)
    dest_slaves = dict()
    for dest_dir in dest_dirs:
        dest_slaves[dest_dir] = scan_slaves(dest_dir)



for dest_dir,slave_dict in dest_slaves.items():
    print("Scanning {}".format(dest_dir))
    for k,v_dest in slave_dict.items():
        v_source = source_slaves.get(k)
        if v_source:
            (dest_slave_path,dest_version_string,dest_date) = v_dest
            (source_slave_path,source_version_string,source_date) = v_source
            if filecmp.cmp(source_slave_path,dest_slave_path,shallow=False):
                continue
            else:
                #print("Files {} and {} are different".format(source_slave_path,dest_slave_path))
                do_update = True

                if source_version_string:
                    if dest_version_string != source_version_string:
                        print("*** updating {} from {} => {}".format(k,source_version_string.rstrip(),dest_version_string.rstrip()))
                else:
                    # no version string found, compare dates
                    if dest_date < source_date:
                        print("*** updating {} (newer by {} days)".format(k,int(source_date-dest_date)//86400))
                if do_update:
                    if not preview:
                        print("====> copy {} {}".format(source_slave_path,dest_slave_path))
                        shutil.copyfile(source_slave_path,dest_slave_path)