#
# mit2mot conversion tool by JOTD
#
# some cases may not be taken into account, but it successfully
# converted Motorola FPSP code (68040 FPU emulation)
#
# for instance:
#
# https://devel.rtems.org/browser/rtems/c/src/lib/libcpu/m68k/m68040/fpsp?rev=f9b93da8b47ff7ea4d6573b75b6077f6efb8dbc6&order=name
#
import re,itertools,os,collections
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--noincludes",action="store_true")
parser.add_argument("--fixduplabels",action="store_true")
parser.add_argument("--showduplabels",action="store_true")
parser.add_argument("--optimize",action="store_true")
parser.add_argument("input_file")
parser.add_argument("output_file")

args = parser.parse_args()
if os.path.abspath(args.input_file) == os.path.abspath(args.output_file):
    raise Exception("Define an output file which isn't the input file")

def convert_size(m):
    inst = m.group(2)
    instprefix = inst[:-1]
    if instprefix in {"or"} or (len(inst)>3 and inst.lower() not in {"bfins","bfexts","addx",
                            "subx","roxl"}):
        last = inst[-1]
        if last in "blswxd":
            inst = "{}.{}".format(instprefix,last)
    return m.group(1)+inst

def is_register(arg):
    # not complete
    return bool(re.match("[ad][0-7]|fp[0-7]|fpcr|fpiar|fpsr|ccr|sr|vbr",arg.lower()))

def optimize_pc(m):
    blank,opcode,blank2,arg1 = m.groups()
    if not is_register(arg1):
        arg1 += "(pc)"
    return "{}{}{}{},".format(blank,opcode,blank2,arg1)
def optimize_jump(m):
    blank,opcode,rest = m.groups()
    if opcode == "jmp":
        opcode = "bra"
    elif opcode == "jsr":
        opcode = "bsr"

    return "{}{}{}".format(blank,opcode,rest)

regexes = [
# de-collate suffix : moveb => move.b
(r"^(\w*:?[ \t]+)(\w+)",convert_size),
# C-style comments
("//",";"),
# indirect addressing with data register & shift (68020)
("%(a[0-7])@\(%(d[0-7]):([lw]):(\d+)\)",r"(\1,\2.\3*\4)"),
# indirect addressing with data register no shift
("%(a[0-7])@\(%(d[0-7]):([lw])\)",r"(\1,\2.\3)"),
# remove % for regs
(r"([{/:\s\(,\-])%",r"\1"),
# remove immediate # sign in some cases
("([{:])#",r"\1"),
# change hex prefix
("0x","$"),
# remove global directive
("(\.global)",r";|\1"),
# convert data directives
("(\s)\.long",r"\1dc.l"),
("(\s)\.short",r"\1dc.w"),
("(\s)\.byte",r"\1dc.b"),
# | is comment at start
("^(\s*)\|",r"\1;"),
# | is comment if followed by space
(r"\|\s","; "),
# un-pipe xref/end/section (maybe would be better to remove)
(r"^(\s+)\|(xref|end|section)",r"\1\2"),
# SET directive => =
("^\s+\.set\s+(\S+?),(\S+)",r"\1 = \2"),
# remove SYM wrapper (from asm.h?)
("SYM\((\w+)\)",r"\1"),
]

if args.noincludes:
    regexes.append(("([\.#]include)\s.*",""))
else:
    regexes.append(("^(\s+)[\.#](include\s+)",r"   \2"))

if args.optimize:
    regexes.append(("^(\s+)(\w+\.?\w?)(\s+)([a-z_]\w+),",optimize_pc))
    regexes.append(("^(\s+)(jsr|jmp)(\s+\w+)",optimize_jump))

regexes = [(re.compile(s,re.IGNORECASE|re.M),r) for s,r in regexes]


with open(args.input_file) as f:
    lines = f.read()
    for s,r in regexes:
        lines = s.sub(r,lines)

if args.fixduplabels or args.showduplabels:
    reps = set()
    # print redefined stuff
    c = collections.Counter(re.findall("^(\w+):",lines,flags=re.M))
    for k,v in c.items():
        if v>1:
            reps.add(k)
    if reps:
        print("{} duplicate labels found".format(len(reps)))
        for k,v in c.items():
            if v>1:
                print("{} defined {} times".format(k,v))
        if args.fixduplabels:
            # convert to local labels, see what happens
            # that's brutal and fails if there are nonlocal labels
            # in between
            for rep in reps:
                lines = re.sub(r"\b{}\b".format(rep),"."+rep,lines)



with open(args.output_file,"w") as f:
    f.write(lines)





