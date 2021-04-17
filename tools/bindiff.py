import sys,re,os
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("-f","--first",required=True)
parser.add_argument("-s","--second",required=True)
parser.add_argument("-t","--third")
parser.add_argument("-m","--mode",default="all",help="difference mode: all, third")

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

if not args.third:
    for i,(c1,c2) in enumerate(zip(*data)):
        if c1 != c2:
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
