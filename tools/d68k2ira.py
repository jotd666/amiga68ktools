import sys,re,os
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("d68k_file")
parser.add_argument("ira_file")

# always use d68k DLO option (datalogic off) or RLO (rts logic off)

args = parser.parse_args()

infile = args.d68k_file
outfile = args.ira_file

sizedict = {"b":1,"w":2,"l":4}
instruction_re = re.compile("([0-9A-F]{6})\s+([0-9A-F _~]+)\t+(\S.*)")
label_re = re.compile(r"\bL00([0-9A-F]{4})\b")
label_re_2 = re.compile(r"\bLAB_([0-9A-F]{4})\b")
size = 0
with open(infile) as f,open(outfile,"w") as fw:
    section_offset = 0
    o = 0
    fw.write("; converted by d68k2ira.py (C) 2020-2021 JOTD\n\nABSEXECBASE = 4\n\n")
    for line in f:
        inst = None
        line = label_re.sub(r"LAB_\1",line.rstrip())
        line = re.sub("^\s+(LAB_)",r"\1",line)
        line = line.replace("MOVEA.L\t$0004,","MOVEA.L\tABSEXECBASE,")
        im = instruction_re.match(line)
        if im:
            offset,hexstring,instruction = im.groups()
            instruction = instruction.split(";")[0].strip().split("\t")
            if len(instruction)==1:
                instruction = instruction[0]
            else:
                instruction = "{:8s}{}".format(*instruction)
            hexstring = hexstring.replace(" ","")
            hexstring = hexstring.replace("_","")
            hexstring = hexstring.replace("~","")
            o = int(offset,16) + section_offset
            if instruction.startswith("dc."):
                inst = "\t{:28s} ;{:06x}".format(instruction,o)
                size = sizedict[instruction[3]]
            else:
                inst = "\t{:28s} ;{:06x}: {}".format(instruction,o,hexstring.lower())
                size = len(hexstring)//2

        elif "\tSECTION" in line:
            section_offset = o+size
            inst = line[4:]
        else:
            lm = label_re_2.match(line)
            if lm:
                inst = line

        if inst:
            fw.write(inst)
            fw.write("\n")
