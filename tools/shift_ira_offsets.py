import sys,re,os
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("offset",help="value of offset to add/sub (decimal/hex with $ or 0x)")
parser.add_argument("-n","--negate",action="store_true")
parser.add_argument("ira_in_file")
parser.add_argument("ira_out_file")

# to run with a negative offset use "--" to break from options:
# shift_ira_offsets.py -- -$20000 src.s out.s

args = parser.parse_args()

offset = args.offset

# try to figure out offset, hex, decimal
if offset.isdigit():
    offset = int(offset)
elif offset.startswith("0x"):
    offset = int(offset,16)
elif offset.startswith("$"):
    offset = int(offset.replace("$",""),16)

if args.negate:
    offset = -offset

print("Applying ${:x} offset shift".format(offset))

infile = args.ira_in_file
outfile = args.ira_out_file

def shift_offset(m):
    v = m.group(1)
    l = len(v)
    return ";{v:0{l}x}".format(l=l,v=int(v,16)+offset)

with open(infile) as fr, open(outfile,"w") as fw:
    for line in fr:
        line = re.sub(";(\w+)",shift_offset,line)
        fw.write(line)