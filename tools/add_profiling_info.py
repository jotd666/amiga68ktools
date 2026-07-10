# reads a json file and computes 3 frequency ranges
# adds those freqs to the source file
#
# {  "('8EB9', 'cp   $01')": 15556,
#  "('8EBB', 'jp   z,$8FA1')": 15556,
#  "('8EBE', 'jr   c,$8ED9')": 4359,
#  "('8ED9', 'dec  (ix+$15)')": 1789,
#  "('8EDC', 'jp   z,$8F93')": 1789 }

import re,itertools,os,collections,json
import argparse,ast


instruction_with_offset_re = re.compile("\t\w.*\|\s+\[\$(....)")

parser = argparse.ArgumentParser()

parser.add_argument("asm_file")
parser.add_argument("json_file")


args = parser.parse_args()

with open(args.json_file) as f:
    info = {int(ast.literal_eval(k)[0],16):v for k,v in json.load(f).items()}

max_count = max(info.values())

nb_parts = 3
limit = [((i)*max_count)//nb_parts for i in range(1,nb_parts)]


lines = []
with open(args.asm_file) as f:
    for line in f:
        m = instruction_with_offset_re.match(line)
        if m:
            address = int(m.group(1),16)
            if address in info:
                count = info[address]
                if count > limit[1]:
                    rate = "high"
                elif count > limit[0]:
                    rate = "medium"
                else:
                    rate = "low"
                count = (count*100)//max_count
                line = re.sub(" \[freq=.*","",line)
                line = line.rstrip() + f" [freq={rate}, count={count}%]\n"
        lines.append(line)

print(f"updating asm file {args.asm_file}...")
# yes, we overwrite the file. Not very safe...
with open(args.asm_file,"w") as f:
    f.write("".join(lines))





