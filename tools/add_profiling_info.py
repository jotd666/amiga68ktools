
import re,itertools,os,collections,json
import argparse,ast
import os,re,pathlib

instruction_re = re.compile("(\w{4}):")


def get_trace(tn):
    pcs = collections.Counter()
    with tn.open() as f:
        nb_inst = 0
        for line in f:
            m = instruction_re.match(line)
            if m:
                nb_inst += 1
                pcs[int(m.group(1),0x10)] += 1
    return pcs

instruction_with_offset_re = re.compile("\t\w.*\|\s+\[\$(....)")

parser = argparse.ArgumentParser()

parser.add_argument("asm_file",type=pathlib.Path,help="68000 converted assembly file to update")
parser.add_argument("mame_file",type=pathlib.Path,help="generated with 'trace mame.tr,,noloop'")


args = parser.parse_args()

print(f"reading MAME trace file {args.mame_file}...")

pcs = get_trace(args.mame_file)

max_count = max(pcs.values())

nb_parts = 3
limit = [((i)*max_count)//nb_parts for i in range(1,nb_parts)]

print(f"Updating asm {args.asm_file}...")
lines = []
with open(args.asm_file) as f:
    for line in f:
        m = instruction_with_offset_re.match(line)
        if m:
            address = int(m.group(1),16)
            if address in pcs:
                count = pcs[address]
                if count > limit[1]:
                    rate = "high"
                elif count > limit[0]:
                    rate = "medium"
                else:
                    rate = "low"
                count = (count*100)//max_count
                line = re.sub(" \[freq=.*","",line)
                line = line.rstrip() + f" [freq={rate}, count={count}%]\n"
        lines.append(line)

print(f"Writing asm file {args.asm_file}...")
# yes, we overwrite the file. Not very safe...
with open(args.asm_file,"w") as f:
    f.write("".join(lines))





