#!/usr/bin/env python

import os,sys,json,shutil,struct
import re,collections

import argparse

def doit(rtb_file,output_file):
    with open(rtb_file,"rb") as f:
        f.read(4)   # CRC
        contents = f.read()

    relocs = []
    a3 = iter(contents)

    def nextlong(it):
        return (next(it)<<24)+(next(it)<<16)+(next(it)<<8)+(next(it))

    def reloc1byte():
        nonlocal a2
        a2 += d0
        relocs.append(a2)

    def reloc2bytes():
        nonlocal d0
        # reloc2bytes
        d0 <<= 8
        d0 += next(a3)
        reloc1byte()

    try:
        a2 = 0
        while(True):
            d0 = next(a3)
            if d0:
                reloc1byte()
            else:
                d0 = next(a3)
                if d0:
                    reloc2bytes()
                else:
                    d0 = next(a3)
                    if d0:
                        reloc2bytes()
                    else:
                        d0 = next(a3)
                        if d0:
                            reloc1byte()
                        else:
                            break
        # second pass: BCPL shit
        ffff = nextlong(a3)
        while(True):
            offset = nextlong(a3)
            if not offset:
                break
            #relocs.append(offset)

    except StopIterator:
        pass

    with open(output_file,"w") as out:
        out.write("reloc:\n")
        for k in sorted(relocs):
            out.write("\tdc.l\t${:08x}\t\n".format(k))
        out.write("\tdc.l\t$0\n")
if __name__ == '__main__':
    """
        Description :
            Main application body
    """
    PROGNAME = os.path.basename(sys.argv[0])
    parser = argparse.ArgumentParser()
    parser.add_argument("--rtb-file", help="RTB file",type=str, required=True)
    parser.add_argument("--output-file", help="output file",type=str, required=True)

    args = parser.parse_args()

    doit(args.rtb_file,args.output_file)
