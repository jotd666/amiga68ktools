import re,os
import argparse
parser = argparse.ArgumentParser()
parser.add_argument("file", help="asm error log")

args = parser.parse_args()

r = re.compile("error 3009 .* undefined symbol <(\w+)> at|.*undefined reference to `(\w+)'")

s = set()
with open(args.file) as f:
    for line in f:
        m = r.match(line)
        if m:
            s.add(m.group(1) or m.group(2))
for i in sorted(s):
    print(i)
