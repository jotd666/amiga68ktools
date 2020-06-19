import glob,os,shutil,re,sys

def doit(root_directory,ags_subdir="AGS"):
    ags_directory = os.path.join(root_directory,ags_subdir)
    program_dir = os.path.dirname(__file__ if not hasattr(sys,"frozen") else os.path.dirname(__file__))

    # name of the game extracted from WHDload .slave information
    gamename_dict = {}
    for ags_subdir in glob.glob(os.path.join(ags_directory,"*.ags")):
        for root,dirs,files in os.walk(ags_subdir):
            for f in files:
                f,s = os.path.splitext(f)
                if s == ".run":
                    fs = f.replace("_","").replace("III","3").replace("II","2").lower()
                    gamename_dict[fs] = (root,f)

    img_source = os.path.join(program_dir,"data","images")
    # name of the game extracted from iGame database
    names = {os.path.basename(x).lower().replace("2disk","").replace("&","and") : x for x in glob.glob(os.path.join(img_source,"*","*"))}
    for k,(d,f) in gamename_dict.items():
        image_dir = names.get(k)
        if not image_dir:
            # demo, CD32/CDTV stuff, special edition, "the" prefix
            k = k.replace("floppy","")
            for to_remove in ["^the","demo$","cd..$","se$","special.*edition$","bonus.*$","arcadia$","amigafun$"]:
                image_dir = names.get(re.sub(to_remove,"",k).strip())
                if image_dir:
                    break
        if image_dir:
            shutil.copyfile(os.path.join(image_dir,"igame.iff"),os.path.join(d,"{}.iff".format(f)))

if __name__ == "__main__":
    doit(r"C:\DATA\jff\AmigaHD\PROJETS\CD32GAMES\HDROOT_DEMO\AGS")