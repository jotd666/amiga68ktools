import sys,re,os
import argparse

# report reverse-engineered function names into raw asm code from another processor
#
# sometimes when I transcode a game, I want to convert the game from 6502/Z80 to 68000
# and keep on RE on the 68000 code, as it's more motivating to make it work first and work
# out the details / bugs afterwards.
# so in the end the 68k code is more documented/reversed than the original reversed code
# which is a pity as the reverse of the original code isn't as complete so other ppl have
# to check the 68k converted code to see how it works

parser = argparse.ArgumentParser()
parser.add_argument("input_files",nargs="+")
parser.add_argument("--output_file","-o",help="file to update",action="store")

labels = dict()
equates = dict()

label_re = re.compile("^(\w\w+_[0-9a-f]{4}):",re.I)
hex_label_re = re.compile("^([0-9a-f]{4}):",re.I)
hex_ref_re = re.compile("\$([0-9a-f]{4})",re.I)
equates_re = re.compile("^(\w+_[0-9a-f]{4})\s*=\s*(\w+)")

args = parser.parse_args()

if not args.output_file:
    raise Excception("No output file")

# scan input files
for file in args.input_files:
    with open(file) as f:
        for line in f:
            m = label_re.match(line)
            if m:
                name = m.group(1)
                key = int(name[-4:],16)
                labels[key] = name
            else:
                m = equates_re.match(line)
                if m:
                    equates[int(m.group(2),16)] = m.group(1)

all_addresses = {**labels,**equates}

# open output file

outlines = []
prev_line = ""
with open(args.output_file) as f:
    for line in f:
        orgline = line

        m = hex_label_re.match(line)
        if m:
            address = int(m.group(1),16)
            newlab = labels.get(address)
            if newlab:
                m = label_re.match(prev_line)
                toks = prev_line.split()
                if not m or m.group(1)!= newlab:
                    line = f"{newlab}:\n{line}"
                    # see if we should add a linefeed

                    if any(x in toks for x in ["jp","jmp","rts","ret"]): # Z80/6502 support
                        line = "\n"+line

        line = hex_ref_re.sub(lambda m: all_addresses.get(int(m.group(1),16),"$"+m.group(1)),line)
        outlines.append(line)
        prev_line = orgline

tf = args.output_file+".new"

with open(tf,"w") as f:
    f.writelines(outlines)

if os.path.getsize(tf) < os.path.getsize(args.output_file):
    # small safety
    raise Exception("New file is smaller than the original: not doing anything")
os.remove(args.output_file)
os.rename(tf,args.output_file)

print(all_addresses)