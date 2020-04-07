# find areas that game left untouched (searches for long 0xcccccccc whdload patterns)

import sys

param = sys.argv[1]

with open(param,"rb") as f:
    contents = f.read()

limit = 0x12000
start_offset = -1

for i,c in enumerate(contents):
    if c==0xcc:
        if start_offset == -1:
            start_offset = i
            length = 0
        else:
            length += 1
    else:
        if start_offset != -1 and length > limit:
            print("memory block @ ${:08x}, length ${:08x}".format(start_offset,length))
        start_offset = -1

