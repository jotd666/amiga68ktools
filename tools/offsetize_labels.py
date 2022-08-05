import sys,re,os
import argparse
import ira_asm_tools

# asm input is raw IRA disassembly
# change LAB_xxxx by lb_<offset> in assembly file

parser = argparse.ArgumentParser()
parser.add_argument("asmfile", help="assembly file")
parser.add_argument("--outfile", help="assembly fixed file")
args = parser.parse_args()

asmfile = args.asmfile

af = ira_asm_tools.AsmFile(asmfile)

translation_table = {}

lab_re = re.compile(r"\b(LAB_\w+)")
for label,address in af.label_addresses.items():
    m = lab_re.match(label)
    if m:
        new_label = "lb_{:05x}".format(address)
        translation_table[label] = new_label

with open(args.outfile,"w") as f:
    for line in af.lines:
        new_line = lab_re.sub(lambda m:translation_table.get(m.group(1),m.group(1)),line)
        f.write(new_line)


