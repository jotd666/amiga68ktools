# add "LOG_REGS" macro call in the specified address range with a specified period
# in order to compare cpu traces with MAME cpu traces when porting games to 68k
#
# very specific tool!
{}
import re,itertools,os,collections
import argparse


instruction_with_offset_re = re.compile("\t\w.*\|\s+\[\$(....)")

parser = argparse.ArgumentParser()
parser.add_argument("-s","--start-address",required=True)
parser.add_argument("-e","--end-address",required=True)
parser.add_argument("-p","--period",required=True,type=int)
parser.add_argument("asm_file")


args = parser.parse_args()

start_address = int(args.start_address,16)
end_address = int(args.end_address,16)

counter = 0

lines = []
with open(args.asm_file) as f:
    for line in f:
        m = instruction_with_offset_re.match(line)
        if m:
            address = int(m.group(1),16)
            if start_address <= address <= end_address:
                counter += 1
                if counter == args.period:
                    counter = 0
                    # time to insert a log regs
                    line = f"\tLOG_REGS\t{address:x}   | added by add_reg_log.py\n"+line
        lines.append(line)

print(f"updating asm file {args.asm_file}...")
# yes, we overwrite the file. Not very safe...
with open(args.asm_file,"w") as f:
    f.write("".join(lines))





