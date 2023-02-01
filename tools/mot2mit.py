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
import simpleeval # get it on pypi (pip install simpleeval)

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

regexes_rev = [
# de-collate suffix : moveb => move.b
(r"^(\w*:?[ \t]+)(\w+)",convert_size),
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

regexes_1 = [
# labels without trailing colon
("^(\w+)$",r"\1:"),
# change hex prefix
("\$","0x"),
# change EQU to just "="
(r"\bequ\b","="),
# convert data directives
(r"(\s)dc.l",r"\1.long"),
(r"(\s)dc.w",r"\1.short"),
(r"(\s)dc.b",r"\1.byte"),
# ";" to "*" start comment
("^(\s*);",r"\1*"),
# ";" to "|" for other comments
(";","|"),
# include directive
(r"(\s+)include\b",r"\1.include"),
# include directive
(r"\bxdef\b",r".global"),
# conditionals
(r"\bendc\b",r".endif"),
(r"\bif(n*)d\b",r".if\1def"),
# mnemonic synomyms
(r"\bshs\b",r"scc"),
(r"\bslo\b",r"scs"),
]

##if args.noincludes:
##    regexes.append(("([\.#]include)\s.*",""))
##else:
##    regexes.append(("^(\s+)[\.#](include\s+)",r"   \2"))

##if args.optimize:
##    regexes.append(("^(\s+)(\w+\.?\w?)(\s+)([a-z_]\w+),",optimize_pc))
##    regexes.append(("^(\s+)(jsr|jmp)(\s+\w+)",optimize_jump))

regexes = []
for s,r in regexes_1:
    try:
        regexes.append((re.compile(s,re.IGNORECASE|re.MULTILINE),r))
    except re.error as e:
        raise Exception("{}: {}".format(s,e))



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

# now the hardest part: convert local labels like .1 to 1f or 1b depending on the direction
# for each real label
local_labels = collections.defaultdict(dict)
global_label_re = re.compile("^([^.]\w+):")
local_label_re = re.compile("^(\.\w+):")

current_label = ""

lines = lines.splitlines()

for i,line in enumerate(lines):
    m = global_label_re.match(line)
    if m:
        current_label = m.group(1)
        local_labels[current_label]["line"] = i
    else:
        m = local_label_re.match(line)
        if m:
            # note down the line
            local_labels[current_label][m.group(1)] = i

label_list = sorted(local_labels.items(),key=lambda c:c[1]["line"])
label_list.append(("",{'line':len(lines)}))   # last fake label

def loclab_replace(m,i):
    label = m.group(4)
    # where is the label in the code?
    label_line = label_line_dict.get(label)
    if label_line:
        suffix = "f" if i < label_line else "b"
        label = label_locid_dict[label]+suffix

    return "{}{}{}{}".format(m.group(1),m.group(2),m.group(3),label)

for i in range(len(label_list)-1):
    gl,data = label_list[i]
    if len(data)>1:
        label_line = data["line"]
        next_label_line = label_list[i+1][1]["line"]

        label_line_dict = {k:v for k,v in data.items() if k != "line"}
        label_locid_dict = {k:str(i) for i,k in enumerate(label_line_dict,1)}

        for k,v in label_line_dict.items():
            # replace labels by numeric labels
            toks = lines[v].split(":")
            toks[0] = label_locid_dict[k]
            lines[v] = ":".join(toks)
        # replace labels in instructions now, preserving indentation and comments
        # (this could fail with string dc.bs but doesn't matter for now)
        for i in range(label_line,next_label_line):
            line = lines[i]
            if line.strip().startswith("*"):
                continue
            toks = line.split("|")
            toks[0] = re.sub("(\s+)(\S+)(\s+)(\S+)",lambda m:loclab_replace(m,i),toks[0])
            lines[i] = "|".join(toks)

# now handle rs.x offsets

offset = "0"
def offset_replace(m):
    global offset
    ident,spc2,rs_size,increment = m.groups()
    datasize = {"l":4,"w":2,"b":1}[rs_size.lower()]

    # try to evaluate the offset
    try:
        offset = str(simpleeval.simple_eval(offset))
    except (SyntaxError,simpleeval.NameNotDefined):
        pass

    rval = "{} = {}".format(ident,offset)
    if datasize == 1:
        offset += "+{}".format(increment)
    else:
        if increment.isdigit():
            offset += "+{}".format(int(increment)*datasize)
        else:
            offset += "+{}*{}".format(increment,datasize)
    if offset.startswith("0+"):
        offset = offset[2:]
    return rval

for i,line in enumerate(lines):
    if line.strip()=="rsreset":
        offset = "0"
        lines[i] = ""
    else:
        if line.strip().startswith("*"):
            continue
        toks = line.split("|")
        toks[0] = re.sub(r"(\S+)(\s+)rs\.([wlb])\s+(\w+)",lambda m:offset_replace(m),toks[0],flags=re.I)
        lines[i] = "|".join(toks)

with open(args.output_file,"w") as f:
    f.write("\n".join(lines))





