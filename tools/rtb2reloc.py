
import os,sys,json,shutil,struct
import re,collections

import argparse
import zlib

def doit(rtb_file,output_file):
    with open(rtb_file,"rb") as f:
        crc = struct.unpack(">I",f.read(4))[0]   # CRC
        contents = f.read()
        computed_crc = zlib.crc32(contents)
        # no match
        print("{:x} {:x} {:x}".format(crc,computed_crc,crc ^ 0xDEADFEED))
    relocs = []
    a3 = iter(contents)
    offset = 0

    def nextb(it):
        nonlocal offset
        offset += 1
        return next(a3)

    def nextword(it):
        return (nextb(it)<<24)+(nextb(it)<<16)+(nextb(it)<<8)+(nextb(it))

    def reloc1byte():
        nonlocal a2
        a2 += d0
        relocs.append([a2,False])

    def reloc2bytes():
        nonlocal d0
        # reloc2bytes
        d0 <<= 8
        d0 += nextb(a3)
        reloc1byte()

    try:
        a2 = 0
        while(True):
            d0 = nextb(a3)
            if d0:
                # small distance
                reloc1byte()
            else:
                if offset % 2:
                    z=nextb(a3)
                    if z:
                        print("FUCKKK",hex(offset))
                # distance > 256
                d0 = nextb(a3)

                if d0:
                    # distance < 65536
                    reloc2bytes()
                else:
                    d0 = nextlong(a3)
                    if not d0:
                        break
                    else:
                        print("LONG RELOC!!!",hex(offset),hex(d0))
        # second pass: BCPL shit
        ffff = nextlong(a3)
        while(True):
            offset = nextlong(a3)
            if not offset:
                break
            relocs.append([offset,True])

    except StopIteration:
        pass

    with open(output_file,"w") as out:
        out.write("reloc:\n")
        for k,is_bcpl in sorted(relocs):
            out.write("\tdc.l\t${:08x}\t;{}\n".format(k," BCPL @{:x}".format(k+0xFC0000) if is_bcpl else ""))
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
