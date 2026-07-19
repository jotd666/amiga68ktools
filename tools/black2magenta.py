from PIL import Image,ImageOps
import pathlib
import re,itertools,os,collections
import argparse

# MAME gfx save edition is cool but cannot differentiate background color from black.
# this is pretty f**ing annoying, fortunately, there's always a CLUT in the set which makes the difference
# here it's monochrome palette index 0xD that saves us.

# here there's actually no problem, as there are no real black color used for sprites
# dark colors are (0,17,0) and (17,0,17)


def transform(dst_image,x,y,nonblack_met):
    p = dst_image.getpixel((x,y))
    if not nonblack_met:
        if p == black or p == magenta:  # X/Y pass, second time there's already magenta
            p = magenta  # black => magenta but not full magenta to avoid conflicts
        else:
            nonblack_met = True
        dst_image.putpixel((x,y),p)
    return nonblack_met

def process(source_path,dest_path,tile_width,tile_height,magenta,black):


    dst_image = Image.open(source_path)

    for y in range(dst_image.size[1]):
        # first pass left to right, stop at the first non-black
        for xstart in range(0,dst_image.size[0],tile_width):
            nonblack_met = False
            for x in range(xstart,xstart+tile_width):
                nonblack_met = transform(dst_image,x,y,nonblack_met)
            nonblack_met = False
            for x in reversed(range(xstart,xstart+tile_width)):
                nonblack_met = transform(dst_image,x,y,nonblack_met)

    for x in range(dst_image.size[0]):
        for ystart in range(0,dst_image.size[1],tile_height):
            nonblack_met = False
            for y in range(ystart,ystart+tile_height):
                nonblack_met = transform(dst_image,x,y,nonblack_met)
            nonblack_met = False
            for y in reversed(range(ystart,ystart+tile_height)):
                nonblack_met = transform(dst_image,x,y,nonblack_met)

    # now scan the whole picture and "forest fire" the image if we encounter magenta (not black!)
    # it means that some edge reached magenta. Now only closed surfaces can remain black
    # also some black in the edges have to be reworked

    # pass 1 get black pixels
    black_pixels = set()
    for y in range(dst_image.size[1]):
        for x in range(dst_image.size[0]):
            p = dst_image.getpixel((x,y))
            if p==black:
                black_pixels.add((x,y))

    # pass 2 if magenta somewhere change to black, iterate, variation of forest fire
    # but global to pic (no 16x16 processing, but doesn't matter)

    while True:
        new_blacks = black_pixels.copy()
        found = False
        for x,y in black_pixels:
            for dx in [-1,0,1]:
                for dy in [-1,0,1]:
                    if dx ^ dy: # avoid diagonals
                        if 0 <= x+dx < dst_image.size[0] and 0 <= y+dy < dst_image.size[1]:
                            # within image bounds
                            p = dst_image.getpixel((x+dx,y+dy))
                            if p==magenta:
                                # this pixel becomes transparent as it was beside a magenta pixel
                                dst_image.putpixel((x,y),magenta)
                                new_blacks.discard((x,y))
                                found = True
        if not found:
            # didn't find any more candidates
            break
        # start again with reduced list
        black_pixels = new_blacks


    dst_image.save(dest_path)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-s","--side",help="side of the tile",default=16,type=int)
    parser.add_argument("-m","--magenta",help="rgb triplet (dd,dd,dd) for magenta",default="254,0,254")
    parser.add_argument("input_directory",help="where png pics are",type=pathlib.Path)
    parser.add_argument("output_directory",help="output directory",type=pathlib.Path)
    args = parser.parse_args()
    if args.input_directory.absolute() == args.output_directory.absolute():
        raise Exception("Define an output dir which isn't the input dir")

    tile_width = args.side
    tile_height = tile_width

    magenta = tuple(map(int,args.magenta.split(",")))
    black = (0,0,0)

    args.output_directory.mkdir(exist_ok=True)

    for src in args.input_directory.glob("*.png"):
        dst = args.output_directory / src.name
        process(src,dst,tile_width,tile_height,magenta,black)
