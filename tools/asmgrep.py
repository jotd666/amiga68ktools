import sys,re,os, glob
import argparse
import collections

parser = argparse.ArgumentParser()
parser.add_argument("asmfile", help="assembly file")
parser.add_argument('--pattern', "-p", action='append')
parser.add_argument('--no-regex', "-n", action='store_true')
parser.add_argument('--firstline', "-f", action='store_true')

args = parser.parse_args()

asmfile = args.asmfile
patterns = args.pattern
no_regex = args.no_regex

if not patterns:
    raise Exception("No patterns passed")

if no_regex:
    patterns = [re.escape(x) for x in patterns]

fifo = collections.deque(maxlen=len(patterns))

files = glob.glob(asmfile)

if not files:
    raise Exception("No input file(s)")

for asmfile in files:
    with open(asmfile) as f:
        for i,line in enumerate(f,1):
            fifo.append(line)
            if len(fifo) == len(patterns):
                m = all(re.search(pat,line,flags=re.I) for line,pat in zip(fifo,patterns))
                if m:
                    if args.firstline:
                        print("{}:{}:{}".format(asmfile,i-len(patterns)-1,fifo[0].rstrip()))
                    else:
                        print("{}:{}:\n  {}".format(asmfile,i-len(patterns)-1,"  ".join(fifo)))


