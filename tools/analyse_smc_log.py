import argparse,os,collections,re

import ira_asm_tools

# analyse a WinUAE SMC log (smc enabled + w 0 start len none)
# present unique targets group sources

parser = argparse.ArgumentParser()
##    parser.add_argument("--input", help="output file",type=str, required=True)
##    parser.add_argument("--output", help="output file",type=str, required=True)
parser.add_argument("input_file",help="input file")
parser.add_argument("output_file",help="input file")
parser.add_argument("--offset","-o", help="offset to subtract (in hex)",type=str)
parser.add_argument("--false-alarms","-f", help="false alarm offsets (one per line, in hex)",type=str)
parser.add_argument("--source","-s", help="assembly source to improve log",type=str)

args = parser.parse_args()

if args.offset:
    args.offset = int(args.offset.lstrip("$"),16)
else:
    args.offset = 0

false_alarms = set()
if args.false_alarms:
    with open(args.false_alarms) as f:
        false_alarms = {int(x,16) for x in f}

af = None
if args.source:
    af = ira_asm_tools.AsmFile(args.source)

smc_re = re.compile("SMC at (\w+) .* from (\w+)")

d = collections.defaultdict(set)

with open(args.input_file) as f:
    for line in f:
        m = smc_re.match(line)
        if m:
            target,source = (int(x,16)-args.offset for x in m.groups())
            d[target].add(source)

with open(args.output_file,"w") as f:
    for k,v in sorted(d.items()):
        if k not in false_alarms:
            f.write("write to {:08x} from {}\n".format(k,",".join("{:08x}".format(x) for x in sorted(v))))
            if af:
                line = None
                # add more detail
                for shift in [0,-2,2]:
                    line = af.address_lines.get(k)
                    if line:
                        break
                if line:
                    for i in range(4):
                        f.write("===> {}".format(af.lines[i+line]))
