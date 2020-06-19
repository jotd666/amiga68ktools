import os,csv,glob,re,sys

import whdload_slave


root_dir = sys.argv[1]
accept_no_game_settings = len(sys.argv)>2

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

database_file = "gameinfo.csv"
empty_database_file = "empty_gameinfo.csv"


gamelist = glob.glob(os.path.join(input_dir,"*","*"))



class GameInfo:
    def __init__(self):
        self.extra_opts = ""

global nb_warns
nb_warns=0


def warn(msg):
    global nb_warns
    print("warning: "+msg)
    nb_warns+=1

gamebase_dict = dict()
if os.path.exists(database_file):
    f = open(database_file,"r")
    cr = csv.reader(f,delimiter=';',quotechar='"')
    nb_fields = len(next(cr))
    line=0
    for r in cr:

        line+=1
        g = GameInfo()
        i=0
        if len(r)<nb_fields:
            raise Exception("Error in %s line %d (%s): not enough fields (%d vs %d)" % (database_file,line,r[0],len(r),nb_fields))
        name = r[i]; i+=1
        i+=1  # spik "tested" column
        i+=1
        g.extra_opts = r[i]; i+=1
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


            slave = slave[0]
            ws = whdload_slave.WHDLoadSlave(slave)
            # only process if slave is valid and files not packed
            if ws.valid:
                if ws.game_full_name in game_set:
                    raise Exception("%s is duplicated in directories" % ws.game_full_name)
                game_set.add(ws.game_full_name)
                menu_file_prefix = re.sub("[^\w]","_",ws.game_full_name)
                start_name = menu_file_prefix+".start"
                start_file = os.path.join(menu_dir,start_name)
                text_file = os.path.join(menu_dir,menu_file_prefix+".txt")
                start_file_on_amiga = ":"+menudata_dir+"/"+start_name

                gamedir_on_cd = gamedir[gamedir.find(os.sep)+1:]
                slave_on_cd = os.path.basename(slave)
                line_start = 'C:whdload "'+slave_on_cd+'" PRELOAD '
                line = ""
                slave_keyinfo = ""
                slave_info_2=[]
                #if ws.game_full_name in gamebase_dict:
                #    g = gamebase_dict[ws.game_full_name]
                #    line += g.extra_opts

                line += data_option

                f=open(start_file,"wb")
                f.write("cd {}\n".format(":"+gamedir_on_cd.replace(os.sep,"/")))
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

                f = open(text_file,"wb")

                f.write(ws.slave_copyright+"\n"+ws.slave_info+"\n")
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
