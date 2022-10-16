import sys,os,json
import argparse
import collections


# tool to convert mame hex dump (prefixed by dc.b manually) to replace
# space separated hex values (no $) by comma separated $ values
#
#   dc.b  00 0a 0b => dc.b  $00,$0a,$0b

parser = argparse.ArgumentParser()
parser.add_argument("coverage_dump_file", help="coverage dump binary file")
parser.add_argument("-u","--uncovered", help="prints uncovered instead of covered",action="store_true")
parser.add_argument("-n","--nodefile", help="reads node file and uses it to mark original source with cov info")
parser.add_argument("-a","--asmfile", help="input asm file")
parser.add_argument("-o","--outfile", help="output asm file")

args = parser.parse_args()

with open(args.coverage_dump_file,"rb") as f:
    contents = f.read()


if args.nodefile:
    with open(args.nodefile) as f:
        nodes = {int(k):v for k,v in json.load(f).items()}
    with open(args.asmfile) as f:
        asmlines = f.readlines()

nb_nodes = len(contents)*8
for i,b in enumerate(contents):
    for j in range(8):
        bit = b >> (7-j) & 1
        node_number = i*8+j
        if args.nodefile:
            linenum = nodes.get(node_number)
            if linenum is not None:
                asmlines[linenum] = "   ; <<{}>>\n".format(["uncovered","covered"][bit]) + asmlines[linenum]

        else:
            if bit != args.uncovered:
                print("{}covered {}".format("un" if args.uncovered else "", node_number))

if args.outfile:
    with open(args.outfile,"w") as f:
        f.writelines(asmlines)