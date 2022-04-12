import sys,re,os
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("offset",type=int)
parser.add_argument("ira_in_file")
parser.add_argument("ira_out_file")


args = parser.parse_args()

offset = args.offset
infile = args.ira_in_file
outfile = args.ira_out_file

def shift_offset(m):
    v = m.group(1)
    l = len(v)
    return ";{v:0{l}x}:".format(l=l,v=int(v,16)+offset)

with open(infile) as fr, open(outfile,"w") as fw:
    for line in fr:
        line = re.sub(";(\w+):",shift_offset,line)
        fw.write(line)