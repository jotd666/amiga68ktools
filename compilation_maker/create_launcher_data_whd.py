import os,csv,glob,re,sys,shutil

import whdload_slave

def doit(root_dir,subdirs,database_file,empty_database_file=None):
    # AGS menu generator
    # written by JOTD 2016-2017

    missing_dict = {}
    renaming_dict = {}
    # database file is only needed to rename games from name extracted from slave data
    # other options are CD32 specific (well, some options could be useful but whdload has a nice
    # splash screen to set them dynamically, let the user choose)
    if database_file:
        with open(database_file) as f:
            dialect = csv.Sniffer().sniff(f.read(1024), delimiters=";,")
            f.seek(0)
            cr = csv.reader(f,dialect=dialect)
            next(cr) # skip title
            cr = list(cr)
            renaming_dict = {row[0]:row[1] for row in cr if row[1]}
            custom_opts = {renaming_dict.get(row[0],row[0]):" ".join(x for x in row[3].split() if "CUSTOM" in x) for row in cr}

    packed_files = []
    RUN_SUFFIX = ".run"

    menudata_dir = "AGS"
    main_drive = "SYS"

    menu_dir = os.path.join(root_dir,menudata_dir)
    # cleanup
    for i in glob.glob(os.path.join(menu_dir,"*.ags")):
        for e in ["txt","run","iff"]:
            for j in glob.glob(os.path.join(i,"*.{}".format(e))):
                os.remove(j)

    for games_dir in subdirs:
        input_dir = os.path.join(root_dir,games_dir)

        category_list = [x for x in os.listdir(input_dir) if os.path.isdir(os.path.join(input_dir,x))]

        print("{} categories found".format(len(category_list)))

        game_set = set()

        for category in category_list:
            games_in_category = [x for x in os.listdir(os.path.join(input_dir,category)) if os.path.isdir(os.path.join(input_dir,category,x))]
            print("{} games in category {}".format(len(games_in_category),category))

            categ_menu_dir = os.path.join(menu_dir,category+".ags")
            if not os.path.isdir(categ_menu_dir):
                os.makedirs(categ_menu_dir)

            for gamedir_bn in games_in_category:

                gamedir = os.path.join(input_dir,category,gamedir_bn)

                slave = glob.glob(os.path.join(gamedir,"*.slave"))
                if len(slave)>1:
                    raise Exception("Cannot process %s, %d slaves found" % (gamedir_bn,len(slave)))
                elif len(slave)==1:
                    data_option = ""
                    datapat = glob.glob(os.path.join(gamedir,"data*"))
                    datadir=[]
                    for i in datapat:
                        if os.path.isdir(i):
                            datadir.append(i)
                    if len(datadir)>1:
                        raise Exception("Cannot process %s, %d data dirs found" % (gamedir_bn,len(datadir)))
                    else:
                        if len(datadir)==1:
                            data_option = "DATA="+os.path.basename(datadir[0])
                            data_root = datadir[0]
                        else:
                            data_root = gamedir


                        slave = slave[0]
                        ws = whdload_slave.WHDLoadSlave(slave)
                        # only process if slave is valid and files not packed
                        if ws.valid:
                            # rename if name passed
                            ws.game_full_name = renaming_dict.get(ws.game_full_name,ws.game_full_name)

                            if ws.game_full_name in game_set:
                                raise Exception("%s is duplicated in directories" % ws.game_full_name)
                            game_set.add(ws.game_full_name)
                            menu_file_prefix = re.sub("[^\w]+","_",ws.game_full_name).strip("_")
                            start_name = menu_file_prefix+RUN_SUFFIX
                            start_file = os.path.join(categ_menu_dir,start_name)
                            text_file = os.path.join(categ_menu_dir,menu_file_prefix+".txt")

                            gamedir_on_cd = "{}:{}".format(main_drive,gamedir[len(root_dir)+1:])
                            slave_on_cd = os.path.basename(slave)
                            line_start = 'C:whdload "'+slave_on_cd+'" PRELOAD '
                            if ws.game_full_name in custom_opts:
                                line_start += custom_opts[ws.game_full_name] + " "
                            else:
                                missing_dict[ws.game_full_name] = ""
                            line = ""
                            slave_keyinfo = ""
                            slave_info_2=[]

                            line += data_option

                            f=open(start_file,"wb")
                            s = 'cd "{}"\n'.format(gamedir_on_cd.replace(os.sep,"/"))
                            f.write(s.encode("latin-1"))
                            s = (line_start+line).strip()+"\n"
                            f.write(s.encode("latin-1"))
                            f.close()

                            fl = ws.game_full_name[0].upper()
                            if fl>='A' and fl<='Z':
                                pass
                            else:
                                fl = "0-9"

                            # escape quotes
                            padding = 40-len(ws.game_full_name)


                            f = open(text_file,"wb")
                            s =ws.slave_copyright+"\n"+ws.slave_info+"\n"
                            f.write(s.encode("latin-1"))
                            f.close()
    if empty_database_file:
        with open(empty_database_file,"w") as f:
            # dummy, this is a database designed for CD32load
            f.write("Name,Alt name,joypad,extra opts,J1 red,J1 blue,J1 yellow,J1 play,J1 green,J1 fwd,J1 bwd,J1 fwdbwd,J0 red,J0 blue,J0 yellow,J0 play,J0 green,J0 fwd,J0 bwd,J0 fwdbwd\n")
            for k in sorted(missing_dict):
                f.write("{},,no,PRELOAD,,,,,,,,,,,,,,,,\n".format(k))

if __name__=="__main__":
    if len(sys.argv)<4:
        print("Usage: {} rootdir database_file".format(os.path.basename(__file__)))
    doit(sys.argv[1],[sys.argv[2]],sys.argv[3])

