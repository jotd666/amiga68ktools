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

if h == "d98112f18792ee3714df16a6eb421b89":
    print("2.3 original ROM, patching...")
    contents[0x38707] = 2
    with open(outfile,"wb") as f:
        f.write(contents)
elif h == "89da1838a24460e4b93f4f0c5d92d48d":
    print("1.0 ROM, unsupported")
elif h == "fc7f68c6df62b494574c25520226a326":
    print("2.3 original cdfs.library, patching...")
    contents[0x31E7] = 2
    with open(outfile,"wb") as f:
        f.write(contents)

elif h == "27df2662a0539fbf48235f2837f00e19":
    print("2.3 patched rom, doing nothing")
elif h == "78e2695573d403edb92e0cd9a67bc653":
    print("cdfs.library already patched, doing nothing")
else:
    print("unknown version MD5 {}".format(h))

