#
# mit2mot conversion tool by JOTD
#
# some cases may not be taken into account, but it successfully
# converted Motorola FPSP code (68040 FPU emulation)
#
# remove "LOG_REGS" lines added by add_reg_log tool
import re,itertools,os
import argparse


log_regs_re = re.compile("\tLOG_REGS.*added by")

parser = argparse.ArgumentParser()

parser.add_argument("asm_file")


args = parser.parse_args()


counter = 0

lines = []
with open(args.asm_file) as f:
    for line in f:
        m = log_regs_re.match(line)
        if m:
            continue
        lines.append(line)

print(f"updating asm file {args.asm_file}...")

with open(args.asm_file,"w") as f:
    f.write("".join(lines))





