import os,csv,glob,re,sys,csv,shutil,time
import find,fnmatch,filecmp

import whdload_slave
import json

preview = False


if True:
    projects = r"K:\jff\AmigaHD\PROJETS"
    source_dir = os.path.join(projects,r"HDInstall\DONE")

    root_dir = os.path.join(projects,source_dir)

    f = find.Find()
    readme_list = f.init(root_dir,pattern_list=["readme"])
    for readme in readme_list:
        with open(readme,"rb") as f:
            contents = f.read()
        if b"mantis.whdload.de" not in contents and b"WHDLoad WWW-Page." in contents:
            print("fixing "+readme)
            contents = contents.replace(b"WHDLoad WWW-Page.\n",b"""WHDLoad WWW-Page or create a mantis issue directly
 at http://mantis.whdload.de
""")
            with open(readme,"wb") as f:
                f.write(contents)
