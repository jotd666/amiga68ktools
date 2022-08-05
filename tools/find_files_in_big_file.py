import re,itertools,glob,os
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("big_file")
parser.add_argument("small_files_directory")

args = parser.parse_args()

with open(args.big_file,"rb") as f:
    contents = f.read()

found = []
for file in glob.glob(os.path.join(args.small_files_directory,"**"),recursive=True):
    if os.path.isfile(file):
        with open(file,"rb") as f:
            sc = f.read()

        offset = contents.find(sc)
        if offset != -1:
            found.append([offset,file,len(sc)])

for offset,file,size in sorted(found):
    print("Found {} (size = ${:x}) at offset ${:x}".format(file,size,offset))
