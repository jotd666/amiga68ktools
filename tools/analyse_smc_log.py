import argparse,os,collections,re

# analyse a WinUAE SMC log (smc enabled + w 0 start len none)
# present unique targets group sources

parser = argparse.ArgumentParser()
##    parser.add_argument("--input", help="output file",type=str, required=True)
##    parser.add_argument("--output", help="output file",type=str, required=True)
parser.add_argument("input_file",help="input file")
parser.add_argument("output_file",help="input file")
parser.add_argument("--offset","-o", help="offset to subtract (in hex)",type=str)

args = parser.parse_args()

if args.offset:
    args.offset = int(args.offset.lstrip("$"),16)
else:
    args.offset = 0

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
        f.write("{:08x} : {}\n".format(k,",".join("{:08x}".format(x) for x in sorted(v))))
