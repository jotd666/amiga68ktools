import sys,os,shutil
import argparse,whdload_slave

parser = argparse.ArgumentParser()
parser.add_argument("root", help="root of games to scan")

args = parser.parse_args()

input_root = args.root


d = dict()

# pass 1: collect years in slaves
# if there are several slaves in the same dir, the last slave found
# overwrites the first(s)

nb_old_slaves = 0

for root,_,files in os.walk(input_root):
    for f in files:
        if f.lower().endswith(".slave"):
            slave_file = os.path.join(root,f)
            slave = whdload_slave.WHDLoadSlave(slave_file)
            if slave.error:
                continue

            if 512*1024 < slave.basemem_size <= 1024*1024 and "ReqAGA" not in slave.flags_list:
                print("{}: {}k".format(slave_file,slave.basemem_size//1024))