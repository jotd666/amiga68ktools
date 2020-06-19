import os,csv,glob,re,sys

import whdload_slave

def doit(root_dir,database_file = "gameinfo.csv",empty_database_file = "empty_gameinfo.csv"):
    cd32load_opt_string = ("DATA/K,CUSTOM/K,CUSTOM1/K/N,CUSTOM2/K/N,CUSTOM3/K/N,CUSTOM4/K/N,CUSTOM5/K/N,FORCECHIP/K,FORCEEXP/K,FORCEOPT/S,"+\
    "NTSC/S,PAL/S,BUTTONWAIT/S,FILTEROFF/S,D/S,PRETEND/S,NOVBRMOVE/S,CPUCACHE/S,IDEHD/S,RNCD/S,DISKUNIT/K/N,"+\
    "JOYPAD/K/N,JOY1RED/K,JOY1GREEN/K,JOY1YELLOW/K,JOY1BLUE/K,JOY1FWD/K,JOY1BWD/K,JOY1PLAY/K,JOY1FWDBWD/K,"+\
    "JOY1RIGHT/K,JOY1LEFT/K,JOY1UP/K,JOY1DOWN/K,"+\
    "JOY0RED/K,JOY0GREEN/K,JOY0YELLOW/K,JOY0BLUE/K,JOY0FWD/K,JOY0BWD/K,JOY0PLAY/K,JOY0FWDBWD/K,"+\
    "JOY0RIGHT/K,JOY0LEFT/K,JOY0UP/K,JOY0DOWN/K,"+\
    "VK/K,VM/K,VMDELAY/K/N,VMMODDELAY/K/N,VMMODBUT/K,"+\
    "CDBUFFER/K,CDBUFFER2/K,FREEBUFFER/K,NB_READ_RETRIES/K/N,CDFREEZE/S,NOBUFFERCHECK/S,READDELAY/K/N,RESLOAD_TOP/K,"+\
    "FILECACHE/S,PRELOAD/K,MASKINT6/S,NOAKIKOPOKE/S").split(",")

    cdopt_dict = dict()

    for cdopt in cd32load_opt_string:
        toks = cdopt.split("/")
        cdopt_dict[toks[0]] = toks[1:]


    packed_files = []
    games_dir = "GAMES*"
    menudata_dir = "MenuData"
    input_dir = os.path.join(root_dir,games_dir)
    menu_dir = os.path.join(root_dir,menudata_dir)
    if not os.path.isdir(menu_dir):
        os.mkdir(menu_dir)
    # cleanup
    for s in glob.glob(os.path.join(menu_dir,"*.txt")):
        os.remove(s)
    for s in glob.glob(os.path.join(menu_dir,"*.start")):
        os.remove(s)




    gamelist = glob.glob(os.path.join(input_dir,"*","*"))

    joypad_type = ["no","joy0","joy1","full"]

    csv_title = ["Name","joypad","extra opts"]
    for j in ["J1","J0"]:
        for i in ["red","blue","yellow","play","green","fwd","bwd","fwdbwd"]:
            csv_title.append(j+" "+i)

    keycode_dict = dict()
    for i in range(1,10):
        keycode_dict[str(i)] = i

    for i in range(0,11):
        keycode_dict["F"+str(i+1)] = i+0x50
    for i,c in enumerate("QWERTYUIOP"):
        keycode_dict[c] = i+0x10
    for i,c in enumerate("ASDFGHJKL"):
        keycode_dict[c] = i+0x20
    for i,c in enumerate("<ZXCVBNM,./"):
        keycode_dict[c] = i+0x30

    keycode_dict["0"] = 0xA
    keycode_dict["LEFT"] = 0x4F
    keycode_dict["RIGHT"] = 0x4E
    keycode_dict["UP"] = 0x4C
    keycode_dict["DOWN"] = 0x4D
    keycode_dict["TAB"] = 0x42
    keycode_dict["HELP"] = 0x5F
    keycode_dict["RETURN"] = 0x44
    keycode_dict["ENTER"] = 0x43
    keycode_dict["ESC"] = 0x45
    keycode_dict["DEL"] = 0x46
    keycode_dict["LALT"] = 0x64
    keycode_dict["LAMIGA"] = 0x66
    keycode_dict["RALT"] = 0x64
    keycode_dict["ALT"] = 0x64
    keycode_dict["RAMIGA"] = 0x67
    keycode_dict["SPACE"] = 0x40
    keycode_dict["LSHIFT"] = 0x60
    keycode_dict["RSHIFT"] = 0x61
    keycode_dict["CTRL"] = 0x63
    keycode_dict["NONE"] = 0x00
    for i,k in enumerate([0x0F,0x1D,0x1E,0x1F,0x2D,0x2E,0x2F,0x3D,0x3E,0x3F]):
        keycode_dict["KP%d" % (i)] = k

    kclc=dict()
    reverse_dict = dict()
    for k,v in keycode_dict.iteritems():
        kclc[k.lower()] = v
        reverse_dict[v]=k

    keycode_dict.update(kclc)

    class GameInfo:
        def __init__(self):
            self.joypad = joypad_type[-1]
            self.extra_opts = ""
            self.j1_red = ""
            self.j1_blue = ""
            self.j1_yellow = ""
            self.j1_play = ""
            self.j1_green = ""
            self.j1_fwd = ""
            self.j1_bwd = ""
            self.j1_fwdbwd = ""
            self.j0_red = ""
            self.j0_blue = ""
            self.j0_yellow =""
            self.j0_play = ""
            self.j0_green = ""
            self.j0_fwd = ""
            self.j0_bwd = ""
            self.j0_fwdbwd = ""

    global nb_warns
    nb_warns=0


    def encode_keycode(v,k):
        rval=["",""]
        if v!="":
            if v.startswith("0x"):
                pass
            elif v[0]=='$':
                v = "0x"+v[1:]
            else:
                if v in keycode_dict:
                    v = "0x"+hex(keycode_dict[v])[2:]
                else:
                    warn("Unknown keycode %s for %s" % (v,k))
                    v="0x00"
            rval[0]=k+"="+v+" "
            rval[1]=k+" -> "+reverse_dict.get(int(v,16),v)
        return rval

    CUSTOM_TABLE = ["Blue","Yellow","Green","Reverse","Forward"]

    def custom_repl(m):
        custom_idx = int(m.group(1))-1
        return CUSTOM_TABLE[custom_idx]

    def warn(msg):
        global nb_warns
        print("warning: "+msg)
        nb_warns+=1

    gamebase_dict = dict()
    if os.path.exists(database_file):
        f = open(database_file,"rb")
        cr = csv.reader(f,delimiter=';',quotechar='"')
        nb_fields = f.readline().count(";")
        line=0
        for r in cr:
            line+=1
            g = GameInfo()
            i=0
            if len(r)<=nb_fields:
                raise Exception("Error in %s line %d (%s): not enough fields (%d vs %d)" % (database_file,line,r[0],len(r),nb_fields))
            name = r[i]; i+=1
            i+=1  # spik "tested" column
            g.joypad = r[i]; i+=1
            g.extra_opts = r[i]; i+=1
            g.j1_red = r[i]; i+=1
            g.j1_blue = r[i]; i+=1
            g.j1_yellow = r[i]; i+=1
            g.j1_play = r[i]; i+=1
            g.j1_green = r[i]; i+=1
            g.j1_fwd = r[i]; i+=1
            g.j1_bwd = r[i]; i+=1
            g.j1_fwdbwd = r[i]; i+=1
            g.j0_red = r[i]; i+=1
            g.j0_blue = r[i]; i+=1
            g.j0_yellow = r[i]; i+=1
            g.j0_play = r[i]; i+=1
            g.j0_green = r[i]; i+=1
            g.j0_fwd = r[i]; i+=1
            g.j0_bwd = r[i]; i+=1
            g.j0_fwdbwd = r[i]; i+=1
            gamebase_dict[name] = g

        f.close()

    empty_gamebase_dict = dict()

    guides_dir = os.path.join(root_dir,"guides")
    if os.path.isdir(guides_dir):
        pass
    else:
        os.mkdir(guides_dir)

    guide_file = os.path.join(guides_dir,"games.guide")

    guide_entry = dict()

    game_set = set()

    for gamedir in gamelist:
        gamedir_bn = os.path.basename(gamedir)
        game_state = os.path.basename(os.path.dirname(gamedir))     # U/NW/OK

        slave = glob.glob(os.path.join(gamedir,"*.slave"))
        if len(slave)>1:
            warn("Cannot process %s, %d slaves found" % (gamedir_bn,len(slave)))
        elif len(slave)==1:
            data_option = ""
            datapat = glob.glob(os.path.join(gamedir,"data*"))
            datadir=[]
            for i in datapat:
                if os.path.isdir(i):
                    datadir.append(i)
            if len(datadir)>1:
                warn("Cannot process %s, %d data dirs found" % (gamedir_bn,len(datadir)))
            else:
                if len(datadir)==1:
                    data_option = "DATA="+os.path.basename(datadir[0])
                    data_root = datadir[0]
                else:
                    data_root = gamedir

                files_packed = False
                max_file_size = 0
                has_disk1 = False
                for root,dirs,files in os.walk(data_root):
                    for fil in files:
                        if os.path.basename(fil).lower()=="disk.1":
                            has_disk1=True


                        filepath = os.path.join(root,fil)
                        f = open(filepath,"rb")
                        z=f.read(4)
                        f.close()
                        if z=="XPKF":
                            warn("File %s is XPKF packed" % os.path.join(root,fil))
                            packed_files.append(os.path.join(root,fil))
                            files_packed = True
                        s = os.path.getsize(filepath)
                        if s>max_file_size:
                            max_file_size = s

                slave = slave[0]
                ws = whdload_slave.WHDLoadSlave(slave)
                # only process if slave is valid and files not packed
                if ws.valid and not files_packed:
                    if ws.game_full_name in game_set:
                        raise Exception("%s is duplicated in directories" % ws.game_full_name)
                    game_set.add(ws.game_full_name)
                    menu_file_prefix = re.sub("[^\w]","_",ws.game_full_name)
                    start_name = menu_file_prefix+".start"
                    start_file = os.path.join(menu_dir,start_name)
                    text_file = os.path.join(menu_dir,menu_file_prefix+".txt")
                    start_file_on_amiga = ":"+menudata_dir+"/"+start_name

                    gamedir_on_cd = gamedir[gamedir.find(os.sep)+1:]
                    slave_on_cd = "CD0:"+gamedir_on_cd.replace(os.sep,"/")+"/"+os.path.basename(slave)
                    line_start = 'cd32load "'+slave_on_cd+'" '
                    line = ""
                    slave_keyinfo = ""
                    slave_info_2=[]
                    if ws.game_full_name in gamebase_dict:
                        g = gamebase_dict[ws.game_full_name]
                        idx=joypad_type.index(g.joypad)
                        line += g.extra_opts+" JOYPAD="+str(idx)+" "

                        if idx>0:
                            kckilist=[]
                            kckilist.append(encode_keycode(g.j0_red,"JOY0RED"))
                            kckilist.append(encode_keycode(g.j0_blue,"JOY0BLUE"))
                            kckilist.append(encode_keycode(g.j0_green,"JOY0GREEN"))
                            kckilist.append(encode_keycode(g.j0_yellow,"JOY0YELLOW"))
                            kckilist.append(encode_keycode(g.j0_play,"JOY0PLAY"))
                            kckilist.append(encode_keycode(g.j0_fwd,"JOY0FWD"))
                            kckilist.append(encode_keycode(g.j0_bwd,"JOY0BWD"))
                            kckilist.append(encode_keycode(g.j0_fwdbwd,"JOY0FWDBWD"))
                            kckilist.append(encode_keycode(g.j0_red,"JOY1RED"))
                            kckilist.append(encode_keycode(g.j1_blue,"JOY1BLUE"))
                            kckilist.append(encode_keycode(g.j1_green,"JOY1GREEN"))
                            kckilist.append(encode_keycode(g.j1_yellow,"JOY1YELLOW"))
                            kckilist.append(encode_keycode(g.j1_play,"JOY1PLAY"))
                            kckilist.append(encode_keycode(g.j1_fwd,"JOY1FWD"))
                            kckilist.append(encode_keycode(g.j1_bwd,"JOY1BWD"))
                            kckilist.append(encode_keycode(g.j1_fwdbwd,"JOY1FWDBWD"))
                            for kc,ki in kckilist:
                                line+=kc
                                if ki!="" and not ki.endswith("NONE"):
                                    slave_info_2.append(ki+"\n")
                    else:
                        empty_gamebase_dict[ws.game_full_name] = GameInfo()
                    line += data_option

                    lup = line.upper()
                    # automatically decide whether to set FILECACHE or not given memory & file constraints
                    # bail out if CDBUFFER or RESLOAD_TOP options are set
                    if "NTSC" not in lup:
                        # useful for AGS menu which sometimes leaves display in NTSC
                        line += " PAL"
                    if "CDBUFFER" not in lup and "RESLOAD_TOP" not in lup and max_file_size+ws.expmem_size+ws.basemem_size<0x1E0000:
                        # no 2MB slave, and max file + max mem does not go beyond CDBUFFER default address
                        # => enables FILECACHE to avoid reading file many times
                        if has_disk1:
                            # even better: if file has a "disk.1" it is very likely that it's accessed first
                            # by LoadFileOffset
                            # (hiscore files are read through LoadFile, not with LoadFileOffset)
                            # in that case, enable PRELOAD of disk.1: no CD access using custom read
                            # at least during startup: less problems when the OS routine is used

                            line += " PRELOAD=disk.1"  # preload implies filecache
                        else:
                            line += " FILECACHE"

                    lup = line.upper().strip()
                    # check if options are valid and not set twice
                    opts = re.split("\s+",lup)
                    opt_found = set()
                    for o in opts:
                        otoks = o.split("=")
                        ok = otoks[0]
                        if ok not in cdopt_dict:
                            raise Exception("%s: Option %s not valid" % (ws.game_full_name,ok))
                        if ok in opt_found:
                            raise Exception("%s: Option %s found more than once" % (ws.game_full_name,ok))
                        opt_found.add(ok)
                        cdopt_quals = cdopt_dict[ok]
                        if "K" in cdopt_quals:
                            if len(otoks)==1:
                                raise Exception("%s: Option %s is a keyword, value required" % (ws.game_full_name,ok))
                            if "N" in cdopt_quals:
                                if otoks[1].isdigit():
                                    pass
                                else:
                                    raise Exception("%s: Option %s is numeric, found %s" % (ws.game_full_name,ok,otoks[1]))

                        if "S" in cdopt_quals and len(otoks)==2:
                            raise Exception("%s: Option %s is a switch, value not allowed" % (ws.game_full_name,ok))


                    f=open(start_file,"wb")
                    f.write((line_start+line).strip()+"\n")
                    f.close()

                    fl = ws.game_full_name[0].upper()
                    if fl>='A' and fl<='Z':
                        pass
                    else:
                        fl = "0-9"
                    if not fl in guide_entry:
                        guide_entry[fl] = []

                    # escape quotes
                    padding = 40-len(ws.game_full_name)

                    guide_entry[fl].append('@{"%s" SYSTEM "c:execute %s"} %s%s\n' % (ws.game_full_name,start_file_on_amiga," "*padding,ws.slave_copyright))

                    # this is for AGS: replace "set customx=1" by "hold blue/yellow..."
                    tweaked_slave_info = re.sub("set custom","Hold CUSTOM",ws.slave_info,flags=re.IGNORECASE)
                    tweaked_slave_info = re.sub("CUSTOM(\d)=1",custom_repl,tweaked_slave_info)
                    tweaked_slave_info = re.sub("hold custom","Set CUSTOM",tweaked_slave_info,flags=re.IGNORECASE)

                    f = open(text_file,"wb")

                    f.write(ws.slave_copyright+ (" (%s)" % game_state)+"\n"+"".join(slave_info_2)+"\n"+tweaked_slave_info)
                    f.close()

    ghandle = open(guide_file,"wb")
    ghandle.write("""@database CD32Load HyperText Game Launcher
    @node main

    Select game first letter

    """)

    nb_items = 0
    for k,gl in sorted(guide_entry.iteritems()):
        ghandle.write('@{" %s " LINK :guides/%s.guide/main  } ' % (k,k))
        nb_items+=1
        if nb_items > 5:
            nb_items=0
            ghandle.write("\n")

        f = open(os.path.join(root_dir,"guides","%s.guide" % k),"wb")
        f.write("""@database CD32Load HyperText Game Launcher
    @node main

    Click game title to play

    """)
        for g in gl:
            f.write(g)
        f.write("@TOC :guides/games.guide/main\n")
        f.write("@endnode\n")
        f.close()

    ghandle.write("\n@endnode\n")
    ghandle.close()

    unpack_files_script = os.path.join(root_dir,"unpack_files")
    if len(packed_files)>0:
        f = open(unpack_files_script,"wb")
        f.write(".key FILE\n") # so classaction recognizes file as a script
        for l in packed_files:
            lr = "/".join((l.split(os.sep)[1:]))

            f.write('xfddecrunch "%s"\n' % lr.replace("(","'(").replace(")","')").replace("#",r"'#"))
        f.close()
    else:
        try:
            os.remove(unpack_files_script)
        except:
            pass
    if len(empty_gamebase_dict)>0:
        f = open(empty_database_file,"w",newline="")
        cw = csv.writer(f,delimiter=';',quotechar='"')
        cw.writerow(csv_title)
        for n in sorted(empty_gamebase_dict.keys()):
            g = empty_gamebase_dict[n]
            cw.writerow([n,"no","full","",g.j1_red,g.j1_blue,g.j1_yellow,g.j1_play,g.j1_green,g.j1_fwd,g.j1_bwd,g.j1_fwdbwd,
            g.j0_red,g.j0_blue,g.j0_yellow,g.j0_play,g.j0_green,g.j0_fwd,g.j0_bwd,g.j0_fwdbwd])

        f.close()
        print("There are %d unconfigured games" % len(empty_gamebase_dict.keys()))
        nb_warns += 1

    else:
        try:
            os.remove(empty_database_file)
        except:
            pass
    if nb_warns>0:
        print("%d warning(s) found" % nb_warns)