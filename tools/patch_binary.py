import re,itertools
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("input_file")
parser.add_argument("search_bytes_file")
parser.add_argument("replace_bytes_file")
parser.add_argument("output_file")

args = parser.parse_args()

with open(args.input_file,"rb") as f:
    contents = f.read()

with open(args.search_bytes_file,"rb") as f:
    search = f.read()

if search[0:-1] in contents:
    with open(args.replace_bytes_file,"rb") as f:
        replace = f.read()
    contents = contents.replace(search,replace)

##    with open(args.output_file,"wb") as f:
##        f.write(contents)
else:
    print("could not find contents of {} in {}".format(args.search_bytes_file,args.input_file))

