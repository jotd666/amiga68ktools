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
parser.add_argument("input_file(s)",nargs="+")
parser.add_argument("--output_file","-o",help="file to update",action="store")



args = parser.parse_args()

if not args.output_file:
    raise Excception("No output file")