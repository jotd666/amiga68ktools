import os,subprocess,hashlib,shutil

amiga_root = r"K:\jff\AmigaHD\PROJETS\HDInstall"
hd_installs = ["DONE","ARetoucher"]

ref_source = os.path.join(amiga_root,hd_installs[0],r"S\SuperfrogHDDev\usr\source\ReadJoypad.s")

def get_md5(source_file):
    with open(source_file,"rb") as f:
        contents = f.read()
    return hashlib.md5(contents).hexdigest()

ref_md5 = get_md5(ref_source)

for hddir in hd_installs:
    for root,dirs,files in os.walk(os.path.join(amiga_root,hddir)):

        for d in dirs:
            if d.lower().endswith("hddev"):
                # dev package found. Try to locate user package
                rdj = os.path.join(root,d,"ReadJoyPad.s")
                if os.path.exists(rdj):
                    cmd5 = get_md5(rdj)
                    if cmd5 != ref_md5:
                        print("needs updating: {}".format(rdj))
                        shutil.copy(ref_source,rdj)
                        with open(os.path.join(root,d,"auto_readjoypad_update.txt"),"w"):
                            pass


