import sys,re,os,json,struct
import argparse
import collections
from itertools import groupby

# how to use:
# 1) hook the VBL with profiler.s
# 2) let run
# 3) activate profiling by setting first longword of marker to 1 (in $100)
# 4) dump the buffer (marker + 4: start, marker + 8: size), note the start address (marker + $C)
# 5) post-process wit this script. start address must be given in hex
#
# the code prints the most frequently reached addresses, grouped by chunks of 0x40 bytes

parser = argparse.ArgumentParser()
parser.add_argument("dump")
parser.add_argument("-s","--start",required=True)

args = parser.parse_args()

d = collections.defaultdict(collections.Counter)

start = int(args.start,16)
discarded = 0
kept = 0
with open(args.dump,"rb") as f:
    contents = f.read()

for i in range(0,len(contents)//8,8):
    pc,stack = struct.unpack_from(">II",contents,i)

    pc -= start

    if 0 < pc < 0x200000:
        kept += 1
        d[(pc//0x40)*0x40][pc] += 1
    else:
        discarded+=1

print("kept: {}, discarded {}".format(kept,discarded))
for counters in d.values():
    print({"{:x}".format(k):v for k,v in counters.items()})
