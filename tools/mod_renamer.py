import fnmatch,os,sys

directory = sys.argv[1]
for module in os.listdir(directory):
    if fnmatch.fnmatch(module,"mod.*"):
        new_name = module[4:]+".mod"
        os.rename(os.path.join(directory,module),os.path.join(directory,new_name))

