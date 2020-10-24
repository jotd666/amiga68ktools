import sys,re,os,hashlib
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("input_file")
parser.add_argument("output_file")


args = parser.parse_args()

infile = args.input_file
outfile = args.output_file
if infile == outfile:
    print("you don't want to overwrite your original file, choose another name")
    sys.exit(1)

with open(infile,"rb") as f:
    contents = bytearray(f.read())

h = hashlib.md5(contents).hexdigest()

# 1.0
# 2.3 d98112f18792ee3714df16a6eb421b89

plist = (
(0x00000452 , 0x0002),
(0x00000504 , 0x0002),
(0x000008b2 , 0x0002),
(0x000008f4 , 0x0002),
(0x00000df0 , 0x0002),
(0x00001a7e , 0x0002),
(0x00001e64 , 0x0002),
(0x00007662 , 0x0002),
(0x000092e4 , 0x0002),
(0x00009342 , 0x0002),
(0x00009446 , 0x0002),
(0x0000a740 , 0x0002),
(0x0000a872 , 0x0002),
(0x0000ae12 , 0x0002),
(0x0000d372 , 0x0002),
(0x0000d472 , 0x0002),
(0x00038706 , 0x0002),
(0x00038d86 , 0x0002),
(0x00000db8 , 0x7202),
(0x0000407c , 0x7202),
(0x000089ba , 0x7202),
(0x0000a004 , 0x7202),
(0x0000a168 , 0x7202),
(0x0000ab54 , 0x7202),
(0x0000acca , 0x7202),
(0x0000eef6 , 0x7202),
(0x0000ef10 , 0x7202),
(0x0000ef2a , 0x7202),
(0x0000ef42 , 0x7202),
(0x00010e88 , 0x7202),
(0x0003b232 , 0x7202),
)

if h == "d98112f18792ee3714df16a6eb421b89":
    print("2.3 original ROM, patching...")
    for offset,word in plist:
        msb = (word >> 8)
        lsb = (word & 0xFF)
        contents[offset] = msb
        contents[offset+1] = lsb
    with open(outfile,"wb") as f:
        f.write(contents)
elif h == "89da1838a24460e4b93f4f0c5d92d48d":
    print("1.0 ROM, unsupported")
elif h == "fc7f68c6df62b494574c25520226a326":
    print("2.3 original cdfs.library, patching...")
    contents[0x31E7] = 2
    with open(outfile,"wb") as f:
        f.write(contents)

elif h == "94799fb3444a305965ea73aceb7348fa":
    print("2.3 patched rom, doing nothing")
elif h == "78e2695573d403edb92e0cd9a67bc653":
    print("cdfs.library already patched, doing nothing")
else:
    print("unknown version MD5 {}".format(h))

