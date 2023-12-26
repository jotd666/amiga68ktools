import sys,re,os
import argparse
from PIL import Image

parser = argparse.ArgumentParser()
parser.add_argument("input_file")
parser.add_argument("output_file")
parser.add_argument("-W",type=int,default=-1)
parser.add_argument("-H",type=int,default=-1)

# always use d68k DLO option (datalogic off) or RLO (rts logic off)

args = parser.parse_args()

infile = args.input_file
outfile = args.output_file
height = args.H
width = args.W

img = Image.open(infile)
if width == -1:
    width = img.size[0]
if height == -1:
    height = img.size[1]

out = Image.new("RGB",(width,height))
box = (0,0,width,height)

out.paste(img)

out.save(outfile)
