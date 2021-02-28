import os,csv,glob,re,sys

import whdload_slave

def doit(root_dir,subdirs,database_file = "gameinfo.csv",empty_database_file = "empty_gameinfo.csv", hard_drive=False, use_jst=False):

    cd32load_opt_string = ("DATA/K,CUSTOM/K,CUSTOM1/K/N,CUSTOM2/K/N,CUSTOM3/K/N,CUSTOM4/K/N,CUSTOM5/K/N,FORCECHIP/K,FORCEEXP/K,FORCEOPT/S,"+
    "NTSC/S,PAL/S,BUTTONWAIT/S,FILTEROFF/S,D/S,PRETEND/S,NOVBRMOVE/S,CPUCACHE/S,IDEHD/S,RNCD/S,DISKUNIT/K/N,"+
    "JOYPAD/K/N,JOY1RED/K,JOY1GREEN/K,JOY1YELLOW/K,JOY1BLUE/K,JOY1FWD/K,JOY1BWD/K,JOY1PLAY/K,JOY1FWDBWD/K,"+
    "JOY1RIGHT/K,JOY1LEFT/K,JOY1UP/K,JOY1DOWN/K,"+
    "JOY0RED/K,JOY0GREEN/K,JOY0YELLOW/K,JOY0BLUE/K,JOY0FWD/K,JOY0BWD/K,JOY0PLAY/K,JOY0FWDBWD/K,"+
    "JOY0RIGHT/K,JOY0LEFT/K,JOY0UP/K,JOY0DOWN/K,"+
    "VK/K,VM/K,VMDELAY/K/N,VMMODDELAY/K/N,VMMODBUT/K,"+
    "CDBUFFER/K,CDBUFFER2/K,FREEBUFFER/K,NB_READ_RETRIES/K/N,CDFREEZE/S,NOBUFFERCHECK/S,READDELAY/K/N,RESLOAD_TOP/K,"+
    "FILECACHE/S,PRELOAD/K,MASKINT6/S,NOAKIKOPOKE/S").split(",")

    cd_only_opt_string = ("D/S,PRETEND/S,CPUCACHE/S,"+
    "CDBUFFER/K,CDBUFFER2/K,FREEBUFFER/K,NB_READ_RETRIES/K/N,CDFREEZE/S,NOBUFFERCHECK/S,READDELAY/K/N,RESLOAD_TOP/K,"+
    "FILECACHE/S,PRELOAD/K,MASKINT6/S,NOAKIKOPOKE/S").split(",")

    if use_jst:
        program = "jst"
        hard_drive = True
    else:
        program = "cd32load"

    menudata_dir = "AGS"
    cdopt_dict = dict()
    cdonly_set = set()

    for cdopt in cd32load_opt_string:
        toks = cdopt.split("/")
        cdopt_dict[toks[0]] = toks[1:]

    for cdopt in cd_only_opt_string:
        toks = cdopt.split("/")
        cdonly_set.add(toks[0])

    menu_dir = os.path.join(root_dir,menudata_dir)
    # cleanup
    for i in glob.glob(os.path.join(menu_dir,"*.ags")):
        for e in ["txt","run","iff"]:
            for j in glob.glob(os.path.join(i,"*.{}".format(e))):
                os.remove(j)

    if not os.path.isdir(menu_dir):
        os.mkdir(menu_dir)

    root_drive = "SYS" if hard_drive else "CD0"

    empty_gamebase_dict = dict()
    game_set = set()
    packed_files = []

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

    def writebin(f,s):
        f.write(s.encode("latin-1"))

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

    joypad_type = ["no","joy0","joy1","full"]

    gamebase_dict = dict()
    if os.path.exists(database_file):
        with open(database_file) as f:
            # detect delimiter automatically
            try:
                dialect = csv.Sniffer().sniff(f.read(1024), delimiters=";,")
            except Exception as e:
                raise Exception("{}: {}".format(database_file,e))
            f.seek(0)
            cr = csv.reader(f,dialect=dialect)
            nb_fields = len(next(cr))
            f.seek(0)

            line=0
            for r in cr:
                line+=1
                g = GameInfo()
                i=0
                if len(r)<nb_fields:
                    r += ['']*(nb_fields-len(r))
                    #raise Exception("Error in %s line %d (%s): not enough fields (%d vs %d)" % (database_file,line,r[0],len(r),nb_fields))
                name = r[i]; i+=1
                g.alias = r[i]; i+=1
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


    for games_dir in subdirs:

        input_dir = os.path.join(root_dir,games_dir)

        gamelist = glob.glob(os.path.join(input_dir,"*","*"))


        csv_title = ["Name","alt name","joypad","extra opts"]
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
        for k,v in keycode_dict.items():
            kclc[k.lower()] = v
            reverse_dict[v]=k

        keycode_dict.update(kclc)



        # create directories for ags categories/folders (1 level only)
        for game_category in {os.path.basename(os.path.dirname(gamedir)) for gamedir in gamelist}:
            ags_subdir = os.path.join(root_dir,menudata_dir,game_category+".ags")
            if os.path.isdir(ags_subdir):
                pass
            else:
                os.mkdir(ags_subdir)

        for gamedir in gamelist:
            gamedir_bn = os.path.basename(gamedir)
            game_category = os.path.basename(os.path.dirname(gamedir))
            ags_subdir = os.path.join(root_dir,menudata_dir,game_category+".ags")

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
                            if z==b"XPKF":
                                warn("File %s is XPKF packed" % os.path.join(root,fil))
                                packed_files.append(os.path.join(gamedir_bn,root[len(root_dir)+1:],fil))
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
                        start_name = menu_file_prefix+".run"
                        start_file = os.path.join(ags_subdir,start_name)
                        text_file = os.path.join(ags_subdir,menu_file_prefix+".txt")

                        current_dir_on_cd = "{}:{}".format(root_drive,gamedir[len(root_dir)+1:]).replace(os.sep,"/")

                        line_start = 'cd "{}"\n{} "{}" '.format(current_dir_on_cd,program,os.path.basename(slave))
                        line = ""
                        slave_keyinfo = ""
                        slave_info_2=[]

                        if ws.game_full_name in gamebase_dict:
                            g = gamebase_dict[ws.game_full_name]
                            g.joypad = g.joypad or "no"
                            try:
                                idx=joypad_type.index(g.joypad)
                            except ValueError:
                                raise Exception("'{}' no in joypad type list for {}".format(g.joypad,ws.game_full_name))
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
                                    if ki and not ki.endswith("NONE"):
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
                        if not use_jst:
                            if hard_drive:
                                line += " IDEHD"

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


                        if use_jst:
                            # remove CD32load options & add QUIET flag
                            line = " ".join([x for x in line.split() if x.split("=")[0].upper() not in cdonly_set] + ["QUIET"])
                        with open(start_file,"wb") as f:
                            writebin(f,(line_start+line).strip()+"\n")


                        fl = ws.game_full_name[0].upper()
                        if fl>='A' and fl<='Z':
                            pass
                        else:
                            fl = "0-9"

                        # escape quotes
                        padding = 40-len(ws.game_full_name)


                        # this is for AGS: replace "set customx=1" by "hold blue/yellow..."
                        tweaked_slave_info = re.sub("set custom","Hold CUSTOM",ws.slave_info,flags=re.IGNORECASE)
                        tweaked_slave_info = re.sub("CUSTOM(\d)=1",custom_repl,tweaked_slave_info)
                        tweaked_slave_info = re.sub("hold custom","Set CUSTOM",tweaked_slave_info,flags=re.IGNORECASE)

                        with open(text_file,"wb") as f:
                            writebin(f,ws.slave_copyright+"\n"+"".join(slave_info_2)+"\n"+tweaked_slave_info)




    unpack_files_script = os.path.join(root_dir,"unpack_files")
    if packed_files:
        f = open(unpack_files_script,"wb")
        writebin(f,".key FILE\n") # so classaction recognizes file as a script
        for l in packed_files:
            lr = "/".join((l.split(os.sep)[1:]))

            writebin(f,'xfddecrunch "%s"\n' % lr.replace("(","'(").replace(")","')").replace("#",r"'#"))
        f.close()
    else:
        try:
            os.remove(unpack_files_script)
        except OSError:
            pass

    if empty_gamebase_dict:
        if empty_database_file:
            with open(empty_database_file,"w",newline="") as f:
                cw = csv.writer(f,dialect=dialect)
                cw.writerow(csv_title)
                for n,g in sorted(empty_gamebase_dict.items()):
                    cw.writerow([n,"","full","",g.j1_red,g.j1_blue,g.j1_yellow,g.j1_play,g.j1_green,g.j1_fwd,g.j1_bwd,g.j1_fwdbwd,
                    g.j0_red,g.j0_blue,g.j0_yellow,g.j0_play,g.j0_green,g.j0_fwd,g.j0_bwd,g.j0_fwdbwd])

        print("There are %d unconfigured games" % len(empty_gamebase_dict))
        nb_warns += 1

    if nb_warns:
        print("%d warning(s) found" % nb_warns)
    if packed_files:
        raise Exception("There are packed files (XPKF). CD32load & JST don't support them."
    "Please run the unpack_files script on the amiga side")

if __name__ == "__main__":
    import sys,os
    progdir=os.path.dirname(__file__)

    doit(sys.argv[1],["GAMES"],database_file = os.path.join(progdir,"gameinfo.csv"),empty_database_file = "empty_gameinfo.csv", hard_drive=False, use_jst=False)
