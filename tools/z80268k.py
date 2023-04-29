import re,itertools,os,collections
import argparse
import simpleeval # get it on pypi (pip install simpleeval)

parser = argparse.ArgumentParser()
parser.add_argument("input_file")
parser.add_argument("output_file")

cli_args = parser.parse_args()
if os.path.abspath(cli_args.input_file) == os.path.abspath(cli_args.output_file):
    raise Exception("Define an output file which isn't the input file")

# input & output comments are "*" and "|" (MIT syntax)
# some day I may set as as an option...
# registers are also hardcoded, and sometimes not coherent (hl = a0, or d5 depending on
# what we do with it)


regexes = []
##for s,r in regexes_1:
##    try:
##        regexes.append((re.compile(s,re.IGNORECASE|re.MULTILINE),r))
##    except re.error as e:
##        raise Exception("{}: {}".format(s,e))

address_re = re.compile("([0-9A-F]{4}):")
# doesn't capture all hex codes properly but we don't care
instruction_re = re.compile("([0-9A-F]{4}):( [0-9A-F]{2}){1,}\s+(\S.*)")

addresses_to_reference = set()

address_lines = {}
lines = []
with open(cli_args.input_file) as f:
    for i,line in enumerate(f):
        m = instruction_re.match(line)
        is_inst = False
        if m:
            address = int(m.group(1),0x10)
            instruction = m.group(3)
            address_lines[address] = i
            txt = instruction.rstrip()
            is_inst = True
        else:
            txt = line.rstrip()
        lines.append((txt,is_inst))

# convention:
# a => d0
# b => d1
# c => d2
# ix => a2
# iy => a3
# and (free use as most of the time there are specifics
# with d and e which make de same for h & l.
# d => d3
# e => d4  (manual rework required!)
# h => d5 or a0 for hl
# l => d6 (manual rework required!)

registers = {
"a":"d0","b":"d1","c":"d2","ix":"a2","iy":"a3","hl":"a0","de":"a1"}  #,"d":"d3","e":"d4","h":"d5","l":"d6",

a_instructions = {"neg":"neg.b\t","cpl":"not.b\t","rra":"roxr.b\t#1,",
                    "rla":"roxl.b\t#1,","rrca":"ror.b\t#1,","rlca":"rol.b\t#1,"}
single_instructions = {"ret":"rts"}

m68_regs = set(registers.values())
m68_data_regs = {x for x in m68_regs if x[0]=="d"}
m68_address_regs = {x for x in m68_regs if x[0]=="a"}

# inverted
rts_cond_dict = {"d2":"bcc","nc":"bcs","z":"bne","nz":"beq","p":"bmi","m":"bpl","po":"bvc","pe":"bvs"}
# d2 stands for c which has been replaced in a generic pass
jr_cond_dict = {"d2":"jcs","nc":"jcc","z":"jeq","nz":"jne","p":"jpl","m":"jmi","po":"jvs","pe":"jvc"}


def f_djnz(args,address,comment):
    target_address = int(args[0],16)
    # a dbf wouldn't work as d1 loaded as byte and with 1 more iteration
    # adapt manually if needed
    addresses_to_reference.add(target_address)
    return f"\tsubq.b\t#1,d1\t| [...]\n\tjne\tl_{target_address:04x}\t{comment}"


def f_bit(args,address,comment):
    return f"\tbtst.b\t#{args[0]},{args[1]}{comment}"

def f_xor(args,address,comment):
    arg = args[0]
    if arg=="d0":
        return f"\tmoveq\t#0,d0{comment}"
    return f"\teor.b\t{arg},d0{comment}"

def f_rl(args,address,comment):
    arg = args[0]
    return f"\troxl.b\t#1,{arg}{comment}"

def f_rlc(args,address,comment):
    arg = args[0]
    return f"\trol.b\t#1,{arg}{comment}"

def f_rr(args,address,comment):
    arg = args[0]
    return f"\troxr.b\t#1,{arg}{comment}"

def f_srl(args,address,comment):
    arg = args[0]
    return f"\tlsr.b\t#1,{arg}{comment}"

def f_sra(args,address,comment):
    arg = args[0]
    return f"\tasr.b\t#1,{arg}{comment}"

def f_sll(args,address,comment):
    arg = args[0]
    return f"\tlsl.b\t#1,{arg}{comment}"

def f_sla(args,address,comment):
    arg = args[0]
    return f"\tasl.b\t#1,{arg}{comment}"

def f_rrc(args,address,comment):
    arg = args[0]
    return f"\tror.b\t#1,{arg}{comment}"

def f_ret(args,address,comment):
    binst = rts_cond_dict[args[0]]
    return f"\t{binst}.b\t0f\n\trts{comment}\n0:"

def f_jp(args,address,comment):
    if len(args)==1:
        address = int(args[0],16)
        jinst = "jra"
    else:
        jinst = jr_cond_dict[args[0]]
        address = int(args[1],16)

    label = f"l_{address:04x}"
    out = f"\t{jinst}\t{label}{comment}"

    # note down that we have to insert a label here
    addresses_to_reference.add(address)

    return out

def f_and(args,address,comment):
    p = args[0]
    out = None
    if p == "d0":
        out = f"\ttst.b\td0{comment}"
    elif p in m68_regs:
        out = f"\tand.b\t{p},d0{comment}"
    elif p.startswith("0x"):
        out = f"\tand.b\t#{p},d0{comment}"
    return out

def f_add(args,address,comment):
    dest = args[0]
    source = args[1]
    out = None
    if dest in m68_address_regs:
        # not supported
        return

    if source in m68_regs:
        out = f"\tadd.b\t{source},{dest}{comment}"
    elif source.startswith("0x"):
        if int(source,16)<8:
            out = f"\taddq.b\t#{source},{dest}{comment}"
        else:
            out = f"\tadd.b\t#{source},{dest}{comment}"
    else:
        out = f"\tadd.b\t{source},{dest}{comment}"
    return out

def f_sbc(args,address,comment):
    dest = args[0]
    source = args[1]
    out = None
    if dest in m68_address_regs:
        # not supported
        return

    if source in m68_regs:
        out = f"\tsubx.b\t{source},{dest}{comment}"
    elif source.startswith("0x"):
        out = f"\tsubx.b\t#{source},{dest}{comment}"
    else:
        out = f"\tsubx.b\t{source},{dest}{comment}"
    return out

def f_sub(args,address,comment):
    dest = "d0"
    source = args[0]
    out = None
    if source in m68_regs:
        out = f"\tsub.b\t{source},{dest}{comment}"
    elif source.startswith("0x"):
        if int(source,16)<8:
            out = f"\tsubq.b\t#{source},{dest}{comment}"
        else:
            out = f"\tsub.b\t#{source},{dest}{comment}"
    else:
        out = f"\tsub.b\t{source},{dest}{comment}"
    return out

def gen_addsub(args,address,comment,inst):
    dest = args[0]
    source = args[1] if len(args)==2 else "d0"
    out = None
    if source in m68_regs:
        out = f"\t{inst}.b\t{source},{dest}{comment}"
##    elif p.startswith("0x"):
##        if int(p,16)<8:
##            out = f"\t{inst}q.b\t#{p},d0{comment}"
##        else:
##            out = f"\t{inst}.b\t#{p},d0{comment}"
    return out

def address_to_label(s):
    return s.strip("()").replace("0x","l_")

def f_or(args,address,comment):
    p = args[0]
    out = None

    if p.startswith("0x"):
        out = f"\tor.b\t#{p},d0{comment}"
    else:
        out = f"\tor.b\t{p},d0{comment}"
    return out

def f_call(args,address,comment):
    func = args[0]
    out = ""
    if len(args)==2:
        cond = func
        func = args[1]
    if func.startswith("0x"):
        func = f"l_{int(func,16):04x}"
    if len(args)==2:
        out = f"\t{rts_cond_dict[cond]}\t0f\n"

    out += f"\tjbsr\t{func}{comment}"
    if len(args)==2:
        out += f"\n0:"
    return out

def f_cp(args,address,comment):
    p = args[0]
    out = None
    if p in m68_regs:
        out = f"\tcmp.b\t{p},d0{comment}"
    elif p.startswith("0x"):
        out = f"\tcmp.b\t#{p},d0{comment}"
    return out

def f_dec(args,address,comment):
    p = args[0]
    size = "w" if p in ["de","hl"] else "b"
    out = f"\tsubq.{size}\t#1,{p}{comment}"

    return out

def f_inc(args,address,comment):
    p = args[0]
    size = "w" if p[0]=="a" else "b"
    out = f"\taddq.{size}\t#1,{p}{comment}"
    return out

def f_ld(args,address,comment):
    dest,source = args[0],args[1]
    out = None
    direct = False

    if dest in m68_regs:
        if source.startswith("("):
            # direct addressing
            direct = True
            prefix = ""
            srclab = source.strip("()")
            if all(d not in m68_address_regs for d in srclab.split(",")):
                source = address_to_label(source)
        elif source in m68_regs:
            prefix = ""
        else:
            prefix = "#"
        if dest[0]=="a":
            source = address_to_label(source)
            if direct:
                out = f"\tmove.w\t{source}(pc),{dest}{comment}"
            else:
                out = f"\tlea\t{source}(pc),{dest}{comment}"
        else:
            src = f"{prefix}{source}".strip("0")
            if src=="#0x" or src == "#":
                out = f"\tclr.b\t{dest}{comment}"
            else:
                out = f"\tmove.b\t{prefix}{source},{dest}{comment}"
    elif dest.startswith("("):
        destlab = dest.strip("()")
        # don't convert to label if register somewhere (indexed or not)
        # convert only on the other cases
        if all(d not in m68_address_regs for d in destlab.split(",")):
            dest = address_to_label(dest)

        prefix = ""
        if source.startswith("0x"):
            prefix = "#"
        src = f"{prefix}{source}".strip("0")
        if src=="#0x" or src == "#":
            out = f"\tclr.b\t{dest}{comment}"
        else:
            out = f"\tmove.b\t{prefix}{source},{dest}{comment}"


    return out

f_jr = f_jp


converted = 0
instructions = 0
out_lines = []

for i,(l,is_inst) in enumerate(lines):
    out = ""
    old_out = l
    if is_inst:
        instructions += 1
        # try to convert
        toks = l.split("|",maxsplit=1)
        comment = "" if len(toks)==1 else f"\t\t|{toks[1]}"
        # add original z80 instruction
        if not comment:
            comment = "\t\t|"
        inst = toks[0].strip()
        comment += f" [{inst}]"
        itoks = inst.split()
        if len(itoks)==1:
            # single instruction either towards a or without argument
            ai = a_instructions.get(inst)
            if ai:
                out = f"\t{ai}d0{comment}"
            else:
                si = single_instructions.get(inst)
                if si:
                    out = f"\t{si}{comment}"
        else:
            inst = itoks[0]
            args = itoks[1:]
            # other instructions, not single, not implicit a
            conv_func = globals().get(f"f_{inst}")
            if conv_func:
                jargs = args[0].split(",")
                # switch registers now
                jargs = [re.sub(r"\b(\w+)\b",lambda m:registers.get(m.group(1),m.group(1)),a) for a in jargs]
                # replace "+" for address registers and swap params
                jargs = [re.sub("\((a\d)\+(0x[0-9A-F]+)\)",r"(\2,\1)",a,flags=re.I) for a in jargs]
                out = conv_func(jargs,address,comment)
    else:
        out=address_re.sub(r"l_\1:",l)
        # convert tables like xx yy aa bb with .byte
        out = re.sub(r"\s+([0-9A-F][0-9A-F])\b",r",0x\1",out,flags=re.I)
        out = out.replace(":,",":\n\t.byte\t")

    if out and old_out != out:
        converted += 1
    else:
        out = l
    out_lines.append(out+"\n")

for address in addresses_to_reference:
    al = address_lines.get(address)
    if al is not None:
        # insert label at the proper line
        out_lines[al] = f"l_{address:04x}:\n{out_lines[al]}"

# cosmetic: compute optimal position for pipe comments
# make proper lines again
out_lines = "".join(out_lines).splitlines()
# first remove all tabs and spaces before pipe chars
out_lines = [re.sub("\s+\|","|",line) for line in out_lines]
# add spaces & tabs. This isn't going to be perfect, but good
# when tabs are between instructions & operands
nout_lines = []
comment_col = 40
for line in out_lines:
    line = line.rstrip()
    toks = line.split("|",maxsplit=1)
    if len(toks)==2:
        fp = toks[0].rstrip()
        sp = toks[1]
        spaces = " "*(comment_col-len(fp))
        line = f'{fp}{spaces}\t|{sp}'
    nout_lines.append(line+"\n")

with open(cli_args.output_file,"w") as f:
    f.writelines(nout_lines)

print(f"Converted {converted} lines on {len(lines)} total, {instructions} instruction lines")
print(f"Converted instruction ratio {converted}/{instructions} {int(100*converted/instructions)}%")
print("\nPLEASE REVIEW THE CONVERTED CODE CAREFULLY AS IT MAY CONTAIN ERRORS!")




