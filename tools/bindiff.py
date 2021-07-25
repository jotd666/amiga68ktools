import sys,re,os,json
import argparse
from operator import itemgetter
from itertools import groupby

parser = argparse.ArgumentParser()
parser.add_argument("-f","--first",required=True)
parser.add_argument("-s","--second",required=True)
parser.add_argument("-t","--third")
parser.add_argument("-m","--mode",default="all",help="difference mode: all, third")
parser.add_argument("-g","--group")

# always use d68k DLO option (datalogic off) or RLO (rts logic off)

args = parser.parse_args()

def error(msg):
    print(msg)
    sys.exit(1)

if os.path.getsize(args.first) != os.path.getsize(args.second):
    error("first & second files don't have the same size")

if args.third and os.path.getsize(args.first) != os.path.getsize(args.third):
    error("first & third files don't have the same size")

data = []
for name in args.first,args.second,args.third:
    if name:
        with open(name,"rb") as f:
            data.append(f.read())

diffs = []
if not args.third:
    for i,(c1,c2) in enumerate(zip(*data)):
        if c1 != c2:
            diffs.append([i,c1,c2])
            if not args.group:
                print("Diff_offset_12 = ${:04x}  ${:02x} vs ${:02x}".format(i,c1,c2))
else:
    for i,(c1,c2,c3) in enumerate(zip(*data)):
        if args.mode == "all":
            if c1 != c2:
                print("Diff_offset_12 = ${:04x}  ${:02x} vs ${:02x}".format(i,c1,c2))
            if c1 != c3:
                print("Diff_offset_13 = ${:04x}  ${:02x} vs ${:02x}".format(i,c1,c3))
        elif args.mode == "third":
            if c1 == c2 != c3:
                print("Diff_offset_3 = ${:04x}  ${:02x} vs ${:02x}".format(i,c1,c3))


if args.group:
    gd = {}
    data = diffs # [2, 3, 4, 5, 12, 13, 14, 15, 16, 17]
    for k, g in groupby(enumerate(data), lambda t:t[0]-t[1][0]):
        grp = list(map(itemgetter(1), g))
        offset = grp[0][0]
        search = list(f[1] for f in grp)
        replace = list(f[2] for f in grp)
        gd[offset] = [search,replace]

    with open(args.group,"w") as f:
        json.dump(gd,f,indent=2)