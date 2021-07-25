import sys,os
import argparse

# compares 2 binary programs assembled at 2 various locations (but exact same program)
# and extract relocation offsets
# it works if MSB or byte after MSB is different (it aligns on MSB)

parser = argparse.ArgumentParser()
parser.add_argument("-f","--first",required=True)
parser.add_argument("-s","--second",required=True)
parser.add_argument("-o","--output",required=True)

args = parser.parse_args()

if os.path.getsize(args.first) != os.path.getsize(args.second):
    error("first & second files don't have the same size")

data = []
for name in args.first,args.second:
    if name:
        with open(name,"rb") as f:
            data.append(f.read())

diffs = []

it = iter(enumerate(zip(*data)))

for i,(c1,c2) in it:
    if c1 != c2:
        if i%2:
            diffs.append(i-1)
        else:
            diffs.append(i)
            next(it)
        next(it)
        next(it)

with open(args.output,"w") as f:
    i = 0
    for r in diffs:
        if i%8 == 0:
            f.write("\n\tdc.l\t")
        else:
            f.write(",")
        i+=1
        f.write("${:08x}".format(r))
    f.write("\n")