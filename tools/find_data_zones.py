import sys,re,os
import argparse
import ira_asm_tools

# going to find zones with DC.W and instructions with LAB as operands.
# generally not good as LAB can generate wrong values if code is moved

parser = argparse.ArgumentParser()
parser.add_argument("asmfile", help="assembly file")
parser.add_argument("--binfile", help="binary file")
parser.add_argument("--outfile", help="assembly fixed file")
parser.add_argument("--fix-data", help="split dc.l in dc.w",action="store_true")
parser.add_argument("--split-dcl", help="split dc.l in dc.w",action="store_true")
parser.add_argument("--start-offset", help="start offset of binary file in hex ex: 0x8000")
args = parser.parse_args()

asmfile = args.asmfile
if args.binfile:
    if args.start_offset is None:
        raise Exception("start offset needed")
    start_offset = int(args.start_offset,16)
    with open(args.binfile,"rb") as f:
        contents = f.read()

af = ira_asm_tools.AsmFile(asmfile)

prev_i = None

segs = []
# find label lines
for i,line in enumerate(af.lines):
    line = line.strip()
    label = False
    if line.endswith(":"):
        label = True
    elif line.lstrip() == line:
        if "=" not in line and len(line.split())==1:
            label = True
    if label:
        if prev_i is not None:
            segs.append((prev_i,i))
        prev_i = i

# scan label intervals
data_segs = []

for start,end in segs:
    has_dc = False
    has_inst = False
    reported = False
    for i in range(start,end):
        line = af.lines[i]
        new_has_inst = False
        sl = line.split(";")[0]
        lab_in_line =  "LAB_" in sl or "lb_" in sl
        if not has_dc and ira_asm_tools.dc_instruction_re.match(line) and not lab_in_line:
            has_dc = True
        if not has_inst and ira_asm_tools.general_instruction_re.match(line) and lab_in_line:
            new_has_inst = True
        if new_has_inst:
            has_inst = True
        if has_dc and has_inst and not reported:
            print("{}: (range {}-{}): mixed DC/instruction with label".format(i+1,start+1,end+1))
            reported = True
            data_segs.append((start,end))
        if reported and new_has_inst:
            print("    {}".format(line.strip()))

if args.outfile:
    lines = af.lines
    if args.fix_data:
        for start,end in data_segs:
            for i in range(start+1,end):
                line = lines[i]
                sl = line.split(";")[0]
                lab_in_line = "LAB_" in sl or "lb_" in sl
                m =  ira_asm_tools.general_instruction_re.match(line)
                if m and lab_in_line:
                    data = m.group(4)
                    # always split up as words to make label insertion easy
                    lines[i] = ""
                    for j in range(0,len(data),4):
                        lines[i] += "\tdc.w\t${}\t\t;{}\n".format(data[j:j+4],m.group(3))


    for i in range(len(lines)):
        line = lines[i]
        data = None

        m = ira_asm_tools.dc_instruction_re.match(line)
        if args.split_dcl:

            if m and m.group(1).upper() == "DC.L":
                # split line

                data = m.group(2)
                if data.startswith("$"):
                    data = int(data.strip("$"),16)

        if not data and "%split%" in line:  # manual tagging or ORI #0,D0 found
            line = line.replace("%split%","").rstrip()
            if not m:
                # instruction
                m = ira_asm_tools.general_instruction_re.match(line)

            if len(m.group(4))==8:
                data = int(m.group(4),16)
                offset = int(m.group(3),16)
        if not data:
            # look for ORI.B  #0,D0
            m = ira_asm_tools.general_instruction_re.match(line)
            if m and m.group(4) == "0"*8:
                data = int(m.group(4),16)
                offset = int(m.group(3),16)
        if data is not None:
            lines[i] = "\tdc.w\t${:04x}\t\t;{:05x}\n\tdc.w\t${:04x}\t\t;{:05x}\n".format(data>>16,offset,data & 0xFFFF,offset+2)


    # last step: collect labels and remove the unused ones
    lab_re = re.compile("(LAB_....|lb_\w+):")
    label_set = set()
    for line in lines:
        m = lab_re.match(line)
        if m:
            label_set.add(m.group(1))
    lab_use_re = re.compile(".+(LAB_....|lb_\w+)")
    for line in lines:
        m = lab_use_re.match(line)
        if m:
            ln = m.group(1)
            if ln in label_set:
                label_set.remove(ln)
    print("Removing {} unused labels...".format(len(label_set)))

    new_lines = []
    for line in lines:
        m = lab_re.match(line)
        if m and m.group(1) in label_set:
            pass
        else:
            new_lines.append(line)


    with open(args.outfile,"w") as f:
        f.writelines(new_lines)

