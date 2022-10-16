import sys,re,os, glob
import argparse
import collections
import json

# tool to convert mame hex dump (prefixed by dc.b manually) to replace
# space separated hex values (no $) by comma separated $ values
#
#   dc.b  00 0a 0b => dc.b  $00,$0a,$0b

parser = argparse.ArgumentParser()
parser.add_argument("coverage_start_address", help="coverage address (hex)")
parser.add_argument("coverage_max_nb_branches", help="coverage nb branches",type=int)
parser.add_argument("asmfile", help="assembly file")
parser.add_argument("outfile", help="instrumented assembly file (out)")
parser.add_argument("-n","--nodefile", help="branch/line file (out)")

args = parser.parse_args()

asmfile = args.asmfile
outfile = args.outfile

dc_re = re.compile(r"^\s+dc\.([bwl])",flags=re.I)
branch_re = re.compile(r"^\s+(b\w{1,2})\b",flags=re.I)
label_re = re.compile(r"^\.?\w+")

with open(asmfile) as f:
    lines = f.readlines()

node = 0

f = open(outfile,"w") if outfile !="-" else sys.stdout


coverage_start_address = int(args.coverage_start_address,16)
coverage_end_address = args.coverage_max_nb_branches//8+1 + coverage_start_address
f.write(r"""
COV_START_ADDRESS = ${0:x}
COV_END_ADDRESS = ${1:x}

MARK_NODE:MACRO
    move.w  {2},-(a7)
    movem.l a0/d0,-(a7)
    lea     COV_START_ADDRESS+(\1/8),a0
    move.b  (a0),d0
    bset    #7-(\1%8),d0
    move.b  d0,(a0)
    movem.l (a7)+,a0/d0
    move.w  (a7)+,{2}
    ENDM


""".format(coverage_start_address,coverage_end_address,"sr"))

itline = iter(lines)

current_line_number = 0

node_dict = {}
def yield_next_line():
    global current_line_number
    while True:
        line = next(itline)
        current_line_number += 1
        nlc = line.strip()
        # empty or comment: skip
        if not nlc or nlc.startswith(";"):
            f.write(line)
        else:
            break
    return line

try:
    while True:
        # read line which isn't a comment or blank
        line = yield_next_line()
        node_line = ""
        next_line = ""

        m = label_re.match(line)
        if m:
            # check if it's not a macro
            if re.search(":\s*macro",line,flags=re.I):
                m = None
        else:
            m = branch_re.match(line)
            if m and m.group(1).lower() in ["bra","bt","bsr"]:
                # cancel branch
                m = None
        f.write(line)
        if m:
            next_line = yield_next_line()
            m = dc_re.match(next_line)
            if m:
                pass
            else:
                node_line = "\tMARK_NODE\t{}\n".format(node)
                node_dict[node] = current_line_number-1
                node += 1
                if node >= args.coverage_max_nb_branches:
                    raise Exception("Too many branches")
        f.write(node_line)
        f.write(next_line)
except StopIteration:
    pass
    f.write("""
cov_init:
    movem.l a0/a1,-(a7)
    lea  COV_START_ADDRESS,a0
    lea  COV_END_ADDRESS,a1
.loop
    clr.b   (a0)+
    cmp.l   a0,a1
    bne.b   .loop
    movem.l (a7)+,a0/a1
    rts
""")

if outfile != "-":
    f.close()

if args.nodefile:
    with open(args.nodefile,"w") as f:
        json.dump(node_dict,f,indent=2)