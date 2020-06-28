import sys,re,os
import argparse
parser = argparse.ArgumentParser()
parser.add_argument("asm-file", help="assembly file")
parser.add_argument('--pattern', action='append')

args = parser.parse_args()

asmfile = args.asm_file
patterns = args.pattern


print(patterns)


