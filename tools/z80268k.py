import re,itertools,os,collections
import argparse
import simpleeval # get it on pypi (pip install simpleeval)

asm_styles = ("mit","mot")
parser = argparse.ArgumentParser()
parser.add_argument("-i","--input-mode",help="input mode either mot style (comments: ;, hex: $)\n"
"or mit style (comments *|, hex: 0x",choices=asm_styles,default=asm_styles[0])
parser.add_argument("-o","--output-mode",help="output mode either mot style or mit style",choices=asm_styles
,default=asm_styles[0])

parser.add_argument("input_file")
parser.add_argument("output_file")

cli_args = parser.parse_args()
if os.path.abspath(cli_args.input_file) == os.path.abspath(cli_args.output_file):
    raise Exception("Define an output file which isn't the input file")

if cli_args.input_mode == "mit":
    in_comment = "|"
    in_start_line_comment = "*"
    in_hex_sign = "0x"
else:
    in_comment = ";"
    in_start_line_comment = in_comment
    in_hex_sign = "$"

if cli_args.output_mode == "mit":
    out_comment = "|"
    out_start_line_comment = "*"
    out_hex_sign = "0x"
    out_byte_decl = ".byte"
    out_word_decl = ".word"
    out_long_decl = ".long"
else:
    out_comment = ";"
    out_start_line_comment = out_comment
    out_hex_sign = "$"
    out_byte_decl = "dc.b"
    out_long_decl = "dc.l"

# input & output comments are "*" and "|" (MIT syntax)
# some day I may set as as an option...
# registers are also hardcoded, and sometimes not coherent (hl = a0, or d5 depending on
# what we do with it)


regexes = []

special_loop_instructions = {"ldir","cpir","cpdr"}
special_loop_instructions_met = set()

##for s,r in regexes_1:
##    try:
##        regexes.append((re.compile(s,re.IGNORECASE|re.MULTILINE),r))
##    except re.error as e:
##        raise Exception("{}: {}".format(s,e))

address_re = re.compile("^([0-9A-F]{4}):")
# doesn't capture all hex codes properly but we don't care
instruction_re = re.compile("([0-9A-F]{4}):( [0-9A-F]{2}){1,}\s+(\S.*)")

addresses_to_reference = set()

address_lines = {}
lines = []
with open(cli_args.input_file,"rb") as f:
    for i,line in enumerate(f):
        is_inst = False
        line = line.decode(errors="ignore")
        if line.lstrip().startswith((in_start_line_comment,in_comment)):
            ls = line.lstrip()
            nb_spaces = len(line)-len(ls)
            ls = ls.lstrip(in_start_line_comment+in_comment)
            txt = (" "*nb_spaces)+out_start_line_comment+ls.rstrip()
        else:
            m = instruction_re.match(line)
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
# all cpu flags preserved. Careful
#
# C (carry) => d7 trashed to set carry properly (d7 isn't used anywhere else)
# X (extended bit) => same as C but Z80 doesn't have it, and relies on CMP to set carry
# then use rl or rr to get its value. It doesn't work that way on 68k, you have to sub or add
# to change X flag and then be able to use ROXL/ROXR.
#
# additionally:
#
# after ccf, carry is cleared and d7.b !=0,
# after scf, carry is set and d7.b = 0
#
# (useful because push/pop af isn't emulated properly, it would involve R/W of 68000 SR
# or 68020 CCR registers and would make that complex to port/would require supervisor mode,
# or would need to call the protected code from a TRAP to make it transparent)

# Galaxian compute_tangent function had to be adapted for this

registers = {
"a":"d0","b":"d1","c":"d2","d":"d3","e":"d4","h":"d5","l":"d6","ix":"a2","iy":"a3","hl":"a0","de":"a1","bc":"a4"}  #,"d":"d3","e":"d4","h":"d5","l":"d6",

addr2data = {"a4":"d1/d2","a1":"d3/d4"}
addr2data_single = {"a1":"d3","a0":"d5"}

a_instructions = {"neg":"neg.b\t","cpl":"not.b\t","rra":"roxr.b\t#1,",
                    "rla":"roxl.b\t#1,","rrca":"ror.b\t#1,","rlca":"rol.b\t#1,"}
single_instructions = {"nop":"nop","ret":"rts","ldir":"jbsr\tldir","cpir":"jbsr\tcpir",
"scf":"clr.b\td7\n\tcmp.b\t#1,d7",
"ccf":"st.b\td7\n\tcmp.b\t#1,d7"}

m68_regs = set(registers.values())
m68_data_regs = {x for x in m68_regs if x[0]=="d"}
m68_address_regs = {x for x in m68_regs if x[0]=="a"}

# inverted
rts_cond_dict = {"d2":"bcc","nc":"bcs","z":"bne","nz":"beq","p":"bmi","m":"bpl","po":"bvc","pe":"bvs"}
# d2 stands for c which has been replaced in a generic pass
jr_cond_dict = {"d2":"jcs","nc":"jcc","z":"jeq","nz":"jne","p":"jpl","m":"jmi","po":"jvs","pe":"jvc"}

lab_prefix = "l_"

def add_entrypoint(address):
    addresses_to_reference.add(address)

def parse_hex(s):
    s = s.strip("$")
    return int(s,16)

def arg2label(s):
    try:
        address = parse_hex(s)
        return f"{lab_prefix}{address:04x}"
    except ValueError:
        # already resolved as a name
        return s

def f_djnz(args,address,comment):
    target_address = arg2label(args[0])
    if target_address != args[0]:
        add_entrypoint(parse_hex(args[0]))

    # a dbf wouldn't work as d1 loaded as byte and with 1 more iteration
    # adapt manually if needed
    return f"\tsubq.b\t#1,d1\t{out_comment} [...]\n\tjne\t{target_address}\t{comment}"



def f_bit(args,address,comment):
    return f"\tbtst.b\t#{args[0]},{args[1]}{comment}"
def f_set(args,address,comment):
    return f"\tbset.b\t#{args[0]},{args[1]}{comment}"
def f_res(args,address,comment):
    return f"\tbclr.b\t#{args[0]},{args[1]}{comment}"

def f_ex(args,address,comment):
    return f"\texg\t{args[0]},{args[1]}{comment}"
def f_push(args,address,comment):
    reg = args[0]
    dreg = addr2data.get(reg)
    rval = ""
    # play it safe, we don't know what the program needs
    # address or data
    if dreg:
        rval = f"\tmovem.w\t{dreg},-(sp){comment}"
    if args[0]=="af":
        rval = f"\tmove.w\td0,-(sp){comment}"
    elif args[0].startswith("a"):
        rval += f"\n\tmove.l\t{args[0]},-(sp){comment}"
    else:
        rval = f"\tmove.w\t{args[0]},-(sp){comment}"
    return rval

def f_pop(args,address,comment):
    reg = args[0]
    if reg=="af":
        rval = f"\tmove.w\t(sp)+,d0{comment}"
    elif reg.startswith("a"):
        rval = f"\tmove.l\t(sp)+,{reg}{comment}"
    else:
        rval = f"\tmove.w\t(sp)+,{reg}{comment}"
    dreg = addr2data.get(reg)
    if dreg:
        rval += f"\n\tmovem.w\t(sp)+,{dreg}{comment}"

    return rval

def f_xor(args,address,comment):
    arg = args[0]
    if arg=="d0":
        # optim, as xor a is a way to zero a
        return f"\tclr.b\td0{comment}"
    prefix = "#" if arg.startswith(out_hex_sign) else ""
    return f"\teor.b\t{prefix}{arg},d0{comment}"

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
    target_address = None
    if len(args)==1:
        label = arg2label(args[0])
        if args[0] != label:
            # had to convert the address, keep original to reference it
            target_address = args[0]
        jinst = "jra"
    else:
        jinst = jr_cond_dict[args[0]]
        label = arg2label(args[1])
        if args[1] != label:
            # had to convert the address, keep original to reference it
            target_address = args[1]

    out = f"\t{jinst}\t{label}{comment}"

    if target_address is not None:
        # note down that we have to insert a label here
        add_entrypoint(parse_hex(target_address))

    return out

def f_and(args,address,comment):
    p = args[0]
    out = None
    if p == "d0":
        out = f"\ttst.b\td0{comment}"
    elif p in m68_regs:
        out = f"\tand.b\t{p},d0{comment}"
    elif p.startswith(out_hex_sign):
        out = f"\tand.b\t#{p},d0{comment}"
    return out

def f_add(args,address,comment):
    dest = args[0]
    source = args[1]
    out = None
    if dest in m68_address_regs:
        # supported but not sure, must be reviewed
        source = addr2data_single.get(source,source)
        out = f"\tadd.w\t{source},{dest}{comment}\n  ^^^^ review"
        return out

    if source in m68_regs:
        out = f"\tadd.b\t{source},{dest}{comment}"
    elif source.startswith(out_hex_sign):
        if parse_hex(source)<8:
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
    elif source.startswith(out_hex_sign):
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
    elif source.startswith(out_hex_sign):
        if parse_hex(source)<8:
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
##    elif p.startswith(out_hex_sign):
##        if int(p,16)<8:
##            out = f"\t{inst}q.b\t#{p},d0{comment}"
##        else:
##            out = f"\t{inst}.b\t#{p},d0{comment}"
    return out

def address_to_label(s):
    return s.strip("()").replace(in_hex_sign,lab_prefix)

def f_or(args,address,comment):
    p = args[0]
    out = None

    if p.startswith(out_hex_sign):
        out = f"\tor.b\t#{p},d0{comment}"
    else:
        out = f"\tor.b\t{p},d0{comment}"
    return out


def f_call(args,address,comment):
    func = args[0]
    out = ""
    target_address = None

    if len(args)==2:
        cond = func
        func = args[1]

    funcc = arg2label(func)
    if funcc != func:
        target_address = func
    func = funcc
    if len(args)==2:
        out = f"\t{rts_cond_dict[cond]}\t0f\n"

    out += f"\tjbsr\t{func}{comment}"
    if len(args)==2:
        out += f"\n0:"
    if target_address is not None:
        add_entrypoint(parse_hex(target_address))
    return out

def f_cp(args,address,comment):
    p = args[0]
    out = None
    if p in m68_regs or re.match("\(a\d\)",p) or "," in p:
        out = f"\tcmp.b\t{p},d0{comment}"
    elif p.startswith(out_hex_sign):
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
                source_val = None
                try:
                    source_val = parse_hex(source)
                except ValueError:
                    pass
                if source_val is not None and source_val < 0x80:  # heuristic limit
                    # maybe not lea but 16 bit immediate value load
                    dest = addr2data_single.get(dest,dest)
                    out = f"\tmove.w\t#{source},{dest}{comment}"
                else:
                    out = f"\tlea\t{source}(pc),{dest}{comment}"
        else:
            src = f"{prefix}{source}".strip("0")
            if src=="#"+out_hex_sign or src == "#":
                out = f"\tclr.b\t{dest}{comment}"
            elif src.lower()=="#"+out_hex_sign+"ff":
                out = f"\tst.b\t{dest}{comment}"
            else:
                out = f"\tmove.b\t{prefix}{source},{dest}{comment}"
    elif dest.startswith("("):
        destlab = dest.strip("()")
        # don't convert to label if register somewhere (indexed or not)
        # convert only on the other cases
        if all(d not in m68_address_regs for d in destlab.split(",")):
            dest = address_to_label(dest)

        prefix = ""
        if source.startswith(out_hex_sign):
            prefix = "#"
        src = f"{prefix}{source}".strip("0")
        if src=="#"+out_hex_sign or src == "#":
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
        toks = l.split(in_comment,maxsplit=1)
        comment = "" if len(toks)==1 else f"\t\t{out_comment}{toks[1]}"
        # add original z80 instruction
        if not comment:
            comment = "\t\t"+out_comment
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
            if inst in special_loop_instructions:
                special_loop_instructions_met.add(inst)

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
                jargs = [re.sub("\((a\d)\+([^)]+)\)",r"(\2,\1)",a,flags=re.I) for a in jargs]
                # replace hex by hex
                if in_hex_sign != out_hex_sign:
                    # pre convert hex signs in arguments
                    jargs = [x.replace(in_hex_sign,out_hex_sign) for x in jargs]

                out = conv_func(jargs,address,comment)
    else:
        out=address_re.sub(rf"{lab_prefix}\1:",l)
        if not re.search(r"\bdc.[bwl]",out,flags=re.I) and not out.strip().startswith((out_start_line_comment,out_comment)):
            # convert tables like xx yy aa bb with .byte
            out = re.sub(r"\s+([0-9A-F][0-9A-F])\b",r",{}\1".format(out_hex_sign),out,flags=re.I)
            out = out.replace(":,",f":\n\t{out_byte_decl}\t")
        if "dc.w" in out or ".word" in out:
            # those are tables referencing other addresses
            # convert them to long
            outcom = out.split(in_comment)
            args = outcom[0].split()
            if len(args)==2:
                words = args[1].split(",")
                outwords = []
                for w in words:
                    wl = arg2label(w)
                    if wl != w:
                        add_entrypoint(parse_hex(w))
                    outwords.append(wl)
                out = f"\t{out_long_decl}\t{','.join(outwords)}"
                if len(outcom)==2:
                    out += f" {out_comment} {outcom[1]}"
    if out and old_out != out:
        converted += 1
    else:
        out = l
    out_lines.append(out+"\n")

for address in addresses_to_reference:
    al = address_lines.get(address)
    if al is not None:
        # insert label at the proper line
        to_insert = f"{lab_prefix}{address:04x}:\n{out_lines[al]}"
        out_lines[al] = to_insert

# group exact following same instructions ror/rol/add ...
for v in [list(v) for k,v in itertools.groupby(enumerate(out_lines),lambda x:x[1])]:
    repeats = len(v)
    if repeats>1:
        # we have a group
        line,instr = v[0]
        if "#1," in instr:
            grouped = instr.rstrip().replace("#1,",f"#{len(v)},")
            grouped += f" * {len(v)}\n"
            out_lines[line] = grouped
            # delete following lines
            for i in range(line+1,line+len(v)):
                out_lines[i] = ""


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

    if "ldir" in special_loop_instructions_met:
        f.write(f"""
{out_start_line_comment} < A0: source (HL)
{out_start_line_comment} < A1: destination (DE)
{out_start_line_comment} < D1: length (16 bit)
ldir:
    subq.w    #1,d1
0:
    move.b    (a0)+,(a1)+
    dbf        d1,0b
    clr.w    d1
    rts
""")

    if "cpir" in special_loop_instructions_met:
        f.write(f"""
{out_start_line_comment} < A0: source (HL)
{out_start_line_comment} < D1: length to search
{out_start_line_comment} > D0.B value searched for (A)
{out_start_line_comment} > Z flag if found
cpir:
    subq.w    #1,d1
0:
    cmp.b    (a0)+,d0
    beq.b    1f
    dbf        d1,0b
    clr.w    d1
    {out_start_line_comment} not found: unset Z
    cmp.b   #1,d1
1:
    rts
""")


print(f"Converted {converted} lines on {len(lines)} total, {instructions} instruction lines")
print(f"Converted instruction ratio {converted}/{instructions} {int(100*converted/instructions)}%")
print("\nPLEASE REVIEW THE CONVERTED CODE CAREFULLY AS IT MAY CONTAIN ERRORS!")




