import os,subprocess

amiga_root = r"K:\jff\AmigaHD\PROJETS"
hd_installs = ["DONE","ARetoucher","GIVENUP"]
usr_installs = os.path.join(amiga_root,"JOTDHD","MY_INSTALLS")

for hddir in hd_installs:
    for root,dirs,files in os.walk(os.path.join(amiga_root,"HDInstall",hddir)):
        for d in dirs:
            if d.lower().endswith("hddev"):
                # dev package found. Try to locate user package
                user_package = os.path.join(usr_installs,d[0],d[:-3])
                if os.path.isdir(user_package):
                    print("moving user install to {}".format(os.path.join(root,d,"usr")))
                    os.rename(user_package,os.path.join(root,d,"usr"))

# check remaining user packages / cleanup
for letterdirs in os.listdir(usr_installs):
    ldabs = os.path.join(usr_installs,letterdirs)
    if len(os.listdir(ldabs)):
        print("remaining stuff in {}".format(letterdirs))
    else:
        os.rmdir(ldabs)

