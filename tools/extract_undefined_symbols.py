import re,os
import argparse,pathlib

parser = argparse.ArgumentParser()
parser.add_argument("file", help="asm error log")
parser.add_argument("--debug-script", help="MAME disassembly", type=pathlib.Path)

hexre = re.compile("\w+_([a-f0-9]{4})")
args = parser.parse_args()

# vasm
r = re.compile("error 3009 .* undefined symbol <(\w+)> at|.*undefined reference to `(\w+)'")
r2 = re.compile(".*undefined reference to `(\w)'")
s = set()
with open(args.file) as f:
    for line in f:
        m = r.match(line) or r2.match(line)
        if m:
            s.add(m.group(1) or m.group(2))

for i in sorted(s):
    print(i)

addresses = []
for e in s:
    m = hexre.match(e)
    if m:
        i = int(m.group(1),0X10)
        addresses.append(i)

if args.debug_script:
    with open(args.debug_script,"w") as f:
        for n,i in enumerate(sorted(addresses)):
            f.write(f"dasm d-{n:03d}-{i:04x}.asm,{i:04x},20\n")
