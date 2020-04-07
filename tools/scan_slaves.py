import os,csv,glob,re,sys,csv
import fnmatch

import whdload_slave

root_dir = sys.argv[1]
output_dir = sys.argv[2]
if os.path.exists(output_dir):
    pass
else:
    os.mkdir(output_dir)
cache_file = os.path.join(output_dir,"cache.txt")

if False: #os.path.exists(cache_file):
    f = open(cache_file,"r")
    filelist = [l.strip() for l in f]
    f.close()
else:
    filelist = [os.path.join(root,f) for root,_,files in os.walk(root_dir) for f in files]


    with open(cache_file,"w") as f:
        for l in filelist:
            f.write(l)
            f.write("\n")

slave_list = [l for l in filelist if fnmatch.fnmatch(l,"*.slave") and os.path.exists(l)]


slave_dir_base = dict()

nbtot=len(slave_list)
rows = []
a600_candidates = []
c512_candidates = []
for i,slave in enumerate(slave_list):
    print("Analyzing %s (%d of %d)" % (os.path.basename(slave),i+1,nbtot))
    d = os.path.dirname(slave)
    if d in slave_dir_base:
        pass
    else:
        # analyze slave dir
        slave_dir = d+os.sep
        associated_files = filter(lambda l : l.startswith(slave_dir),filelist)
        has_diskfiles = False
        has_cdtv_data = False
        nr = 0
        for a in associated_files:
            df = os.path.basename(a)
            # diskfile pattern (old JST-like style too)
            if "cdtv" in a.lower():
                has_cdtv_data = True
            if fnmatch.fnmatch(df,"disk.[0-9]") or fnmatch.fnmatch(df,"*.d[0-9]"):
                has_diskfiles = True
            else:
                if fnmatch.fnmatch(df,"*.info"):
                    pass
                elif fnmatch.fnmatch(df,"*.slave"):
                    pass
                else:
                    nr+=1

        hd = ["no","yes"][has_diskfiles]
        cd = ["no","yes"][has_cdtv_data]
        slave_dir_base[d] = [hd,nr,cd]

    ws = whdload_slave.WHDLoadSlave(slave)

    hd = slave_dir_base[d][0]
    nr = slave_dir_base[d][1]
    cd = slave_dir_base[d][2]
    copycmd = 'echo R| xcopy /R /S "%s" ' % (os.path.abspath(d))
    copycmd += "%DESTROOT%"+os.sep
    copycmd += '"%s"' % os.path.basename(d)
    row = [ws.game_full_name,ws.slave_info,ws.slave_copyright,hd,nr,cd,ws.basemem_size,ws.expmem_size,ws.basemem_size+ws.expmem_size,",".join(ws.flags_list),ws.kick_string,ws.kick_size,ws.slave,copycmd]
    rows.append(row)
    if (has_cdtv_data or not has_diskfiles) and ws.basemem_size+ws.expmem_size<600000 and ws.kick_size==0:
        a600_candidates.append(row)
    if ws.basemem_size<600000:
        c512_candidates.append(row)

title_line = ["slave","info","copyright","diskfiles","nb_regular_files","has_cdtv","basemem","expmem","totalmem","flags","kick_name","kick_size","path","copycmd"]

output_database = os.path.join(output_dir,"database.csv")
output_a600_database = os.path.join(output_dir,"a600_database.csv")
output_c512_database = os.path.join(output_dir,"chip512_database.csv")
with open(output_database,"w",newline="",encoding="utf-8") as f:
    c = csv.writer(f,delimiter=';',quotechar='"')
    c.writerow(title_line)
    c.writerows(rows)

with open(output_a600_database,"w",newline="",encoding="utf-8") as f:
    c = csv.writer(f,delimiter=';',quotechar='"')
    c.writerow(title_line)
    c.writerows(a600_candidates)

with open(output_c512_database,"w",newline="",encoding="utf-8") as f:
    c = csv.writer(f,delimiter=';',quotechar='"')
    c.writerow(title_line)
    c.writerows(c512_candidates)
