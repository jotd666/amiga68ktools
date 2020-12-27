import os,csv,glob,re,sys,csv,struct,json
import fnmatch

import whdload_slave
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("root_dir")
parser.add_argument("output_dir")
parser.add_argument("-n","--no-cache", help="ignore current cache file",
                    action="store_true")


def get_file_size(pname):
    with open(pname,"rb") as f:
        header = f.read(4)
        if header==b"XPKF":
            rest = f.read(8)
            size = struct.unpack(">I",f.read(4))[0]
            return {"size" : size, "packed" : True}

    return {"size" : os.path.getsize(pname), "packed" : False }

args = parser.parse_args()

root_dir = args.root_dir
output_dir = args.output_dir
if os.path.exists(output_dir):
    pass
else:
    os.mkdir(output_dir)
cache_file = os.path.join(output_dir,"cache.json")

if not args.no_cache and os.path.exists(cache_file):
    with open(cache_file,"r") as f:
        filedict = json.load(f)

else:
    filelist = [os.path.join(root,f) for root,_,files in os.walk(root_dir) for f in files]
    filedict = {n:get_file_size(n) for n in filelist}

    with open(cache_file,"w") as f:
        json.dump(filedict,f,indent=2)

slave_list = [l for l in filedict if fnmatch.fnmatch(l,"*.slave") and os.path.exists(l)]


slave_dir_base = dict()

nbtot=len(slave_list)
rows = []
a600_candidates = []
c512_candidates = []
error_slaves = []
onemeg_total_candidates = []
for i,slave in enumerate(slave_list):
    print("Analyzing %s (%d of %d)" % (os.path.basename(slave),i+1,nbtot))
    d = os.path.dirname(slave)
    if d in slave_dir_base:
        pass
    else:
        # analyze slave dir
        slave_dir = d+os.sep
        associated_files = filter(lambda l : l.startswith(slave_dir),filedict)
        has_diskfiles = False
        has_cdtv_data = False
        nr = 0
        data_files = []
        data_dirs = set()
        data_size = 0
        for a in associated_files:
            df = os.path.basename(a)
            # diskfile pattern (old JST-like style too)
            if "cdtv" in a.lower():
                has_cdtv_data = True
            if fnmatch.fnmatch(df,"*.info"):
                pass
            elif fnmatch.fnmatch(df,"*.slave"):
                pass
            else:
                if fnmatch.fnmatch(df,"disk.[0-9]") or fnmatch.fnmatch(df,"*.d[0-9]"):
                    has_diskfiles = True
                data_files.append(a)
                parts = [x.lower() for x in a.split(os.sep)]
                data_dirs.update(p for p in parts if p.startswith("data-") or p=="data")
                data_size += filedict[a]["size"]
        # how many different "data" dirs are there?

        nr = len(data_files)
        hd = ["no","yes"][has_diskfiles]
        cd = ["no","yes"][has_cdtv_data]
        slave_dir_base[d] = [hd,nr,cd,len(data_dirs)]

    ws = whdload_slave.WHDLoadSlave(slave)
    if ws.error:
        print("Warning: {}".format(ws.error))
        error_slaves.append(ws.error)
    else:
        hd,nr,cd,nbd = slave_dir_base[d]
        if nbd == 0:
            nbd = 1

        copycmd = 'echo R| xcopy /R /S "%s" ' % (os.path.abspath(d))
        copycmd += "%DESTROOT%"+os.sep
        copycmd += '"%s"' % os.path.basename(d)
        row = [ws.game_full_name,ws.slave_info,ws.slave_copyright,hd,nr,nbd,data_size,data_size//nbd,cd,ws.basemem_size,ws.expmem_size,ws.basemem_size+ws.expmem_size,",".join(ws.flags_list),ws.kick_string,ws.kick_size,ws.slave,copycmd]
        rows.append(row)
        if (has_cdtv_data or not has_diskfiles) and ws.basemem_size+ws.expmem_size<600000 and ws.kick_size==0:
            # CD32load A600 compilant games
            a600_candidates.append(row)
        if ws.basemem_size<600000:
            # chipmem = 512k
            c512_candidates.append(row)
        if ws.basemem_size+ws.expmem_size+data_size//nbd < 1024*1024 and ws.kick_size==0:
            # 1MB total mem
            onemeg_total_candidates.append(row)
title_line = ["slave","info","copyright","diskfiles","nb_regular_files","nb_data_dirs","data_size","avg_data_size","has_cdtv","basemem","expmem","totalmem","flags","kick_name","kick_size","path","copycmd"]


def write_database(outfile,rws):
    with open(os.path.join(output_dir,outfile),"w",newline="",encoding="utf-8") as f:
        c = csv.writer(f,delimiter=';',quotechar='"')
        c.writerow(title_line)
        c.writerows(rws)

error_messages = os.path.join(output_dir,"errors.txt")

write_database("database.csv",rows)
write_database("a600_database.csv",a600_candidates)
write_database("chip512_database.csv",c512_candidates)

##onemeg_total_candidates.sort(key=lambda row:row[7])
write_database("cdtv_jst_database.csv",onemeg_total_candidates)

with open(os.path.join(output_dir,"unpack_script"),"wb") as f:
    f.write(b"failat 20\n")
    for filepath,props in filedict.items():
        if props["packed"]:
            cmd = 'xfddecrunch "{}"\n'.format(filepath.replace(os.sep,"/").replace("./",""))
            f.write(cmd.encode())

with open(error_messages,"w") as f:
    for e in error_slaves:
        f.write(e)
        f.write("\n")

