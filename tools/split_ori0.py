import sys,re,os
import argparse
import ira_asm_tools

# asm input is raw IRA disassembly
# change LAB_xxxx by lb_<offset> in assembly file

parser = argparse.ArgumentParser()
parser.add_argument("asmfile", help="assembly file")
parser.add_argument("-o","--outfile", help="assembly fixed file")
args = parser.parse_args()

asmfile = args.asmfile

af = ira_asm_tools.AsmFile(asmfile)

with open(args.outfile,"w") as f:
    for line in af.lines:
        m = ira_asm_tools.general_instruction_re.match(line)
        if m:
            instruction = m.group(1)
            operands = m.group(2)
            offset = m.group(3)
            if instruction == "ORI.B" and operands == "#$00,D0":
                offset = int(offset,16)
                s = "\tdc.w\t$0000\t;{:05x}\n"
                f.write(s.format(offset))
                f.write(s.format(offset+2))
                continue
        f.write(line)


