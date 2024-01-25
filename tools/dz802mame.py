# converts the output of dz80 to the output of MAME Z80 disassembly

import re,itertools,os,collections
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("input_file")
parser.add_argument("output_file")

cli_args = parser.parse_args()

# 000D: 33          inc  sp

if os.path.abspath(cli_args.input_file) == os.path.abspath(cli_args.output_file):
    raise Exception("Define an output file which isn't the input file")

instruction_re = re.compile("([0-9A-F]{4})\s+([0-9A-F]+)\s+([A-Z].*)",flags=re.I)

with open(cli_args.input_file) as f, open(cli_args.output_file,"w") as fw:
    for line in f:
        m = instruction_re.match(line)
        if m:
            offset,hexdata,instruction = m.groups()
            toks = instruction.split(";",maxsplit=1)
            if len(toks)==1:
                comment=""
            else:
                comment = toks[1]
            instruction = toks[0].replace("#","$").lower().rstrip()
            hexdump = " ".join(hexdata[i:i+2] for i in range(0,len(hexdata),2))

            if comment:
                line = f"{offset}: {hexdump:<11} {instruction:<20};{comment}\n"
            else:
                line = f"{offset}: {hexdump:<11} {instruction}\n"
        fw.write(line)























