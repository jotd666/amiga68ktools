#TODO: optimize beq (not .b) etc... by jxx if mit syntax
# also if mit jmp => jra
# CLR_XC_FLAGS    +  addx => addx changed to add
# SET_XC_FLAGS    +  subx => subx changed to sub
#9EB0: 18       clc
#9EB1: 69 08    adc #$08
#9EB3: 85 1B    sta $1b
#9EB5: 90 02    bcc $9eb9  => review flag!!
#
# macro GET_ADDRESS to return pointer on memory layout
# to replace lea/move/... in memory
# extract RAM memory constants as defines, not variables
# work like an emulator
#
# this is completely different from Z80. Easier for registers, but harder
# for memory because of those indexed modes that read pointers from memory
# so we can't really map 32-bit model on original code without heavily adapting everything
#
# on Z80, the ld instruction acted like lea or move, and it was easier to keep separate address
# space for RAM and ROM.

import re,itertools,os,collections,glob,io
import argparse
#import simpleeval # get it on pypi (pip install simpleeval)

asm_styles = ("mit","mot")
parser = argparse.ArgumentParser()
parser.add_argument("-i","--input-mode",help="input mode either mot style (comments: ;, hex: $)\n"
"or mit style (comments *|, hex: 0x",choices=asm_styles,default=asm_styles[1])
parser.add_argument("-o","--output-mode",help="output mode either mot style or mit style",choices=asm_styles
,default=asm_styles[0])
parser.add_argument("-w","--no-review",help="don't insert review lines",action="store_true")
parser.add_argument("-s","--spaces",help="replace tabs by x spaces",type=int)
parser.add_argument("-n","--no-mame-prefixes",help="treat as real source, not MAME disassembly",action="store_true")
parser.add_argument("input_file")
parser.add_argument("output_file")

cli_args = parser.parse_args()

no_mame_prefixes = cli_args.no_mame_prefixes

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
    jsr_instruction = "jbsr"
else:
    out_comment = ";"
    out_start_line_comment = out_comment
    out_hex_sign = "$"
    out_byte_decl = "dc.b"
    out_long_decl = "dc.l"
    jsr_instruction = "jsr"

# input & output comments are "*" and "|" (MIT syntax)
# some day I may set as as an option...
# registers are also hardcoded, and sometimes not coherent (hl = a0, or d5 depending on
# what we do with it)

label_counter = 0
def get_mot_local_label():
    global label_counter
    rval = f".lb_{label_counter}"
    label_counter += 1
    return rval

regexes = []


address_re = re.compile("^([0-9A-F]{4}):")
# doesn't capture all hex codes properly but we don't care
if no_mame_prefixes:
    instruction_re = re.compile("\s+(\S.*)")
else:
    instruction_re = re.compile("([0-9A-F]{4}):( [0-9A-F]{2}){1,}\s+(\S.*)")

addresses_to_reference = set()

address_lines = {}
lines = []
input_files = glob.glob(cli_args.input_file)
if not input_files:
    raise Exception(f"{cli_args.input_file}: no match")

for input_file in input_files:
    with open(input_file,"rb") as f:
        if len(input_files)>1:
            lines.append((f"{out_start_line_comment} input file {os.path.basename(input_file)}",False,None))
        for i,line in enumerate(f):
            is_inst = False
            address = None
            line = line.decode(errors="ignore")
            if line.lstrip().startswith((in_start_line_comment,in_comment)):
                ls = line.lstrip()
                nb_spaces = len(line)-len(ls)
                ls = ls.lstrip(in_start_line_comment+in_comment)
                txt = (" "*nb_spaces)+out_start_line_comment+ls.rstrip()
            else:
                m = instruction_re.match(line)
                if m:
                    if no_mame_prefixes:
                        address = i*0x10  # fake address
                        instruction = m.group(1)
                    else:
                        address = int(m.group(1),0x10)
                        instruction = m.group(3)
                    address_lines[address] = i
                    txt = instruction.rstrip()
                    is_inst = True
                else:
                    txt = line.rstrip()
            lines.append((txt,is_inst,address))


# convention:
# a => d0
# x => d1
# y => d2

# C (carry) => d7 trashed to set carry properly (d7 isn't used anywhere else)
# X (extended bit) => same as C but 6502 doesn't have it, and relies on CMP to set carry

registers = {
"a":"d0","x":"d1","y":"d2","p":"sr","c":"d7","d":"d3",
"v":"d4","dwork1":"d5","dwork2":"d6",
"awork1":"a0"}
inv_registers = {v:k for k,v in registers.items()}



single_instructions = {"nop":"nop",
"rts":"rts",
"txa":f"move.b\t{registers['x']},{registers['a']}",
"tya":f"move.b\t{registers['y']},{registers['a']}",
"tax":f"move.b\t{registers['a']},{registers['x']}",
"tay":f"move.b\t{registers['a']},{registers['y']}",
"dex":f"subq.b\t#1,{registers['x']}",
"dey":f"subq.b\t#1,{registers['y']}",
"dec":f"subq.b\t#1,{registers['a']}",
"inx":f"addq.b\t#1,{registers['x']}",
"iny":f"addq.b\t#1,{registers['y']}",
"inc":f"addq.b\t#1,{registers['a']}",
"pha":f"move.w\t{registers['a']},-(sp)",
"pla":f"move.w\t(sp)+,{registers['a']}",
"php":"PUSH_SR",
"plp":"POP_SR",
"sec":"SET_XC_FLAGS",
"clc":"CLR_XC_FLAGS",
"sec":"SET_XC_FLAGS",
"clc":"CLR_XC_FLAGS",
"sei":"SET_I_FLAGS",
"cli":"CLR_I_FLAGS",
"sed":f"st.b{registers['d']}",
"cld":f"clr.b\t{registers['d']}",
"clv":f"CLR_V_FLAG",
}

m68_regs = set(registers.values())

if cli_args.output_mode == "mot":
    # change "j" by "b"
    jr_cond_dict = {k:"b"+v[1:] for k,v in jr_cond_dict.items()}

lab_prefix = "l_"

def add_entrypoint(address):
    addresses_to_reference.add(address)

def parse_hex(s,default=None):
    is_hex = s.startswith(("$","0x"))
    s = s.strip("$")
    try:
        return int(s,16 if is_hex else 10)
    except ValueError as e:
        if default is None:
            raise
        else:
            return default

def arg2label(s):
    try:
        address = parse_hex(s)
        return f"{lab_prefix}{address:04x}"
    except ValueError:
        # already resolved as a name
        return s


def f_bit(args,comment):
    """bits 7 and 6 of operand are transfered to bit 7 and 6 of SR (N,V);
the zero-flag is set according to the result of the operand AND
the accumulator (set, if the result is zero, unset otherwise).
This allows a quick check of a few bits at once without affecting
any of the registers, other than the status register (SR).

A AND M, M7 -> N, M6 -> V
N    Z    C    I    D    V
M7   +    -    -    -    M6
addressing    assembler    opc    bytes    cycles
zeropage    BIT oper    24    2    3
absolute    BIT oper    2C    3    4

this is way too complex for a very marginal use for overflow
"""
    arg = args[0]
    return f"\ttst.b\t{arg}{comment}"


def f_lda(args,comment):
    return generic_load('a',args,comment)
def f_sta(args,comment):
    return generic_store('a',args,comment)
def f_stx(args,comment):
    return generic_store('x',args,comment)
def f_sty(args,comment):
    return generic_store('y',args,comment)
def f_ldx(args,comment):
    return generic_load('x',args,comment)
def f_ldy(args,comment):
    return generic_load('y',args,comment)

def f_inc(args,comment):
    return generic_indexed_to("addq","#1",args,comment)
def f_dec(args,comment):
    return generic_indexed_to("subq","#1",args,comment)

def generic_load(dest,args,comment):
    return generic_indexed_from("move",dest,args,comment)
def generic_store(src,args,comment):
    return generic_indexed_to("move",src,args,comment)

def f_ora(args,comment):
    return generic_indexed_from("or",'a',args,comment)
def f_asl(args,comment):
    return generic_indexed_from("asl",'a',args,comment)
def f_ror(args,comment):
    return generic_indexed_from("ror",'a',args,comment)
def f_rol(args,comment):
    return generic_indexed_from("ror",'a',args,comment)
def f_and(args,comment):
    return generic_indexed_from("and",'a',args,comment)
def f_adc(args,comment):
    return generic_indexed_from("addx",'a',args,comment)
def f_sbc(args,comment):
    return generic_indexed_from("subx",'a',args,comment)
def f_eor(args,comment):
    return generic_indexed_from("eor",'a',args,comment)
def f_lsr(args,comment):
    return generic_indexed_from("lsr",'a',args,comment)

def generic_indexed_to(inst,src,args,comment):
    arg = args[0]
    if inst.islower():
        inst += ".b"
    regsrc = registers.get(src,src)
    if len(args)>1:
        index_reg = args[1].strip(")")
        if arg.startswith("("):
            if arg.endswith(")"):
                # Y indirect indexed
                load = "move.l"
                arg = arg.strip("()")
            else:
                # X indirect indexed
                arg = arg.strip("(")
                arg2 = index_reg
                return f"""\tlea\t{arg},{registers['awork1']}{comment}
\tadd.w\t{arg2},{registers['awork1']}{comment}
\tmove.l\t({registers['awork1']}),{registers['awork1']}{comment}
    {inst}\t{regsrc},({registers['awork1']}){comment}
"""
        else:
            load = "lea"

        return f"""\t{load}\t{arg},{registers['awork1']}{comment}
    {inst}\t{regsrc},({registers['awork1']},{index_reg}.w){comment}
"""

    else:
        return f"\t{inst}\t{regsrc},{arg}{comment}"


def generic_indexed_from(inst,dest,args,comment):
    arg = args[0]
    if inst.islower():
        inst += ".b"

    if len(args)>1:
        index_reg = args[1]
        return f"""\tlea\t{arg},{registers['awork1']}{comment}
    {inst}\t({registers['awork1']},{index_reg}.w),{registers[dest]}{comment}
"""

    else:
        # various optims
        if inst=="move.b" and arg[0]=='#':
            val = parse_hex(arg[1:])
            if val == 0:
                return f"\tclr.b\t{registers[dest]}{comment}"
            elif val == 0xff:
                return f"\tst.b\t{registers[dest]}{comment}"

        if inst=="eor.b" and arg[0]=='#' and parse_hex(arg[1:])==0xff:
           return f"\tnot.b\t{registers[dest]}{comment}"

    return f"\t{inst}\t{arg},{registers[dest]}{comment}"


def f_jmp(args,comment):
    target_address = None
    label = arg2label(args[0])
    if args[0] != label:
        # had to convert the address, keep original to reference it
        target_address = args[0]

    out = f"\tjmp\t{label}{comment}"

    if target_address is not None:
        # note down that we have to insert a label here
        add_entrypoint(parse_hex(target_address))

    return out

def gen_addsub(args,comment,inst):
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
def address_to_label_out(s):
    return s.strip("()").replace(out_hex_sign,lab_prefix)


def generic_cmp(args,reg,comment):
    p = args[0]
    out = f"\tmove.b\t{p},{registers['dwork1']}{comment}\n\tcmp.b\t{registers[reg]},{registers['dwork1']}{comment}"

    return out


def f_cmp(args,comment):
    return generic_cmp(args,'a',comment)

def f_cpx(args,comment):
    return generic_cmp(args,'x',comment)

def f_cpy(args,comment):
    return generic_cmp(args,'y',comment)



def f_jsr(args,comment):
    func = args[0]
    out = ""
    target_address = None

    funcc = arg2label(func)
    if funcc != func:
        target_address = func
    func = funcc

    out += f"\t{jsr_instruction}\t{func}{comment}"

    if target_address is not None:
        add_entrypoint(parse_hex(target_address))
    return out

def f_bcc(args,comment):
    return f_bcond("cc",args,comment)
def f_bcs(args,comment):
    return f_bcond("cs",args,comment)
def f_bvc(args,comment):
    return f_bcond("vc",args,comment)
def f_bvs(args,comment):
    return f_bcond("vs",args,comment)
def f_beq(args,comment):
    return f_bcond("eq",args,comment)
def f_bne(args,comment):
    return f_bcond("ne",args,comment)
def f_bmi(args,comment):
    return f_bcond("mi",args,comment)
def f_bpl(args,comment):
    return f_bcond("pl",args,comment)

def f_bcond(cond,args,comment):
    func = args[0]
    out = ""
    target_address = None

    funcc = arg2label(func)
    if funcc != func:
        target_address = func
    func = funcc

    out += f"\tb{cond}\t{func}{comment}"

    if target_address is not None:
        add_entrypoint(parse_hex(target_address))
    return out




def is_immediate_value(p):
    srcval = parse_hex(p,"FAIL")
    return srcval != "FAIL"

def can_be_quick(source):
    return parse_hex(source,default=8)<8

def tab2space(line):
    out = []
    nbsp = cli_args.spaces
    for i,c in enumerate(line):
        if c == "\t":
            c = " "*(nbsp-(i%nbsp))
        out.append(c)
    return "".join(out)


converted = 0
instructions = 0
out_lines = []
unknown_instructions = set()

for i,(l,is_inst,address) in enumerate(lines):
    out = ""
    old_out = l
    if is_inst:
        instructions += 1
        # try to convert
        toks = l.split(in_comment,maxsplit=1)
        # add original z80 instruction
        inst = toks[0].strip()

        if no_mame_prefixes:
            comment = f"\t\t{out_comment} [{inst}]"
        else:
            comment = f"\t\t{out_comment} [${address:04x}: {inst}]"
        if len(toks)>1:
            if not toks[1].startswith(" "):
                comment += " "
            comment += toks[1]


        # now we can split according to remaining spaces
        itoks = inst.split(maxsplit=1)
        if len(itoks)==1:
            si = single_instructions.get(inst)
            if si:
                out = f"\t{si}{comment}"

        else:
            inst = itoks[0]
            args = itoks[1:]
            sole_arg = args[0].replace(" ","")
            # pre-process instruction to remove spaces
            # (only required when source is manually reworked, not in MAME dumps)
            #sole_arg = re.sub("(\(.*?\))",lambda m:m.group(1).replace(" ",""),sole_arg)

            # also manual rework for 0x03(ix) => (ix+0x03)
            sole_arg = re.sub("(-?0x[A-F0-9]+)\((\w+)\)",r"(\2+\1)",sole_arg)


            # other instructions, not single, not implicit a
            conv_func = globals().get(f"f_{inst}")
            if conv_func:
                jargs = sole_arg.split(",")
                # switch registers now
                jargs = [re.sub(r"\b(\w+)\b",lambda m:registers.get(m.group(1),m.group(1)),a) for a in jargs]
                # replace "+" or "-" for address registers and swap params
                jargs = [re.sub("\((a\d)\+([^)]+)\)",r"(\2,\1)",a,flags=re.I) for a in jargs]
                jargs = [re.sub("\((a\d)-([^)]+)\)",r"(-\2,\1)",a,flags=re.I) for a in jargs]
                # replace hex by hex
                if in_hex_sign != out_hex_sign:
                    # pre convert hex signs in arguments
                    jargs = [x.replace(in_hex_sign,out_hex_sign) for x in jargs]

                # some source codes have immediate signs, not really needed as if not between ()
                # it is immediate
                try:
                    out = conv_func(jargs,comment)
                except Exception as e:
                    print(f"Problem parsing: {l}, args={jargs}")
                    raise
            else:
                out = f"{l}\n   ^^^^ TODO: unknown/unsupported instruction"
                unknown_instructions.add(inst)
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
for v in [list(v) for k,v in itertools.groupby(enumerate(out_lines),lambda x:x[1].split(out_comment)[0])]:
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
    if line.startswith(".db") and line[3].isspace():
        line = line.replace(".db","\t.byte")
        line = line.replace(in_comment,out_comment)
    elif line.startswith(".dw") and line[3].isspace():
        line = line.replace(".dw","\t.long")
        line = line.replace(in_comment,out_comment)

    nout_lines.append(line+"\n")

# add review flag message in case of move.x followed by a branch
# also add review for writes to unlabelled memory
# also post-optimize stuff
prev_fp = None

reg_a = registers["a"]

for i,line in enumerate(nout_lines):
    line = line.rstrip()
    toks = line.split("|",maxsplit=1)
    if len(toks)==2:
        fp = toks[0].rstrip().split()
        finst = fp[0]
        if finst == "bvc":
            if prev_fp:
                if prev_fp == ["CLR_V_FLAG"]:
                    nout_lines[i-1] = f"{out_start_line_comment} clv+bvc => bra\n"
                    nout_lines[i] = nout_lines[i].replace(finst,"bra.b")
                elif prev_fp[0] == "tst.b":
                    nout_lines[i] += "          ^^^^^^ TODO: handle bit 6 of operand / change overflow test\n"
            else:
                nout_lines[i] += "          ^^^^^^ TODO: warning: stray bvc test\n"
        elif finst == "bvs":
            if prev_fp:
                if prev_fp[0] == "tst.b":
                    nout_lines[i] += "          ^^^^^^ TODO: handle bit 6 of operand / change overflow test\n"
            else:
                nout_lines[i] += "          ^^^^^^ TODO: warning: stray bvs test\n"

        elif finst == "bcc":
            # if previous instruction sets X flag properly, don't bother, but rol/ror do not!!
            if prev_fp:
                if prev_fp == ["CLR_XC_FLAG"]:
                    nout_lines[i-1] = f"{out_start_line_comment} clc+bcc => bra\n"
                    nout_lines[i] = nout_lines[i].replace(finst,"bra.b")
        elif finst == "bcs":
            # if previous instruction sets X flag properly, don't bother, but rol/ror do not!!
            if prev_fp:
                if prev_fp == ["SET_XC_FLAG"]:
                    nout_lines[i-1] = f"{out_start_line_comment} sec+bcs => bra\n"
                    nout_lines[i] = nout_lines[i].replace(finst,"bra.b")
        elif finst == "rts":
            # if previous instruction sets X flag properly, don't bother, but rol/ror do not!!
            if prev_fp:
                if prev_fp == ["move.w","d0,-(sp)"]:
                    nout_lines[i] += "          ^^^^^^ TODO: review push to stack+return\n"


        if len(fp)>1:
            args = fp[1].split(",")
            if len(args)==2:
                if args[1].startswith("0x"):
                    nout_lines[i] += "          ^^^^^^ TODO: review absolute 16-bit address write\n"
                elif args[0].startswith("0x"):
                    nout_lines[i] += "       ^^^^^^ TODO: review absolute 16-bit address read\n"

        # TODO: set overflow + bvc, set carry + bcs ... => bra

        prev_fp = fp
# post-processing

if cli_args.spaces:
    nout_lines = [tab2space(n) for n in nout_lines]


f = io.StringIO()

if True:
    C = registers['c']
    V = registers['v']

    f.write(f""" {out_start_line_comment} Converted with 6502to68k by JOTD
{out_start_line_comment}
{out_start_line_comment} make sure you call "cpu_init" first so bits 8-15 of data registers
{out_start_line_comment} are zeroed out so we can use (ax,dy.w) addressing mode
{out_start_line_comment} without systematic masking

""")

    if cli_args.output_mode == "mit":
        f.write(f"""\t.macro CLEAR_XC_FLAGS
\tmoveq\t#0,{C}
\troxl.b\t#1,{C}
\t.endm
\t.macro SET_XC_FLAGS
\tst\t{C}
\troxl.b\t#1,{C}
\t.endm

\t.macro CLEAR_V_FLAG
\tmoveq\t#0,{V}
\tadd.b\t{V},{V}
\t.endm

\t.macro SET_I_FLAGS
^^^^ TODO: insert interrupt disable code here
\t.endm
\t.macro CLEAR_I_FLAGS
^^^^ TODO: insert interrupt enable code here
\t.endm
\t.ifdef\tMC68020
\t.macro PUSH_SR
\tmove.w\tccr,-(sp)
\t.endm
\t.macro POP_SR
\tmove.w\t(sp)+,ccr
\t.endm
\t.else
\t.macro PUSH_SR
\tmove.w\tsr,-(sp)
\t.endm
\t.macro POP_SR
\tmove.w\t(sp)+,sr
\t.endm
\t.endif
\t.macro ADD_WITH_CARRY\t\\value,\\operand
\tbcc.b\t0f
\taddq.b\t#1,\\operand
0:
\taddq.b\t\\value,\\operand
\t.endm
\t.macro SUB_WITH_CARRY\t\\value,\\operand
\tbcc.b\t0f
\tsubq.b\t#1,\\operand
0:
\tsubq.b\t\\value,\\operand
\t.endm
\t.endm
\t.endif
""")
    else:
        f.write(f"""\tCLEAR_XC_FLAGS:MACRO
\tmoveq\t#0,{C}
\troxl.b\t#1,{C}
\tENDM
\tSET_XC_FLAGS:MACRO
\tst.b\t{C}
\troxl.b\t#1,{C}
\tENDM

\tCLEAR_V_FLAG:MACRO
\tmoveq\t#0,{V}
\tadd.b\t{V},{V}
\tENDM

\tSET_I_FLAGS:MACRO
^^^^ TODO: insert interrupt disable code here
\tENDM
\tCLEAR_I_FLAGS:MACRO
^^^^ TODO: insert interrupt enable code here
\tENDM
""")

    f.write("cpu_init:\n")
    for i in range(8):
        f.write(f"\tmoveq\t#0,d{i}\n")
    f.write("\trts\n\n")

buffer = f.getvalue()+"".join(nout_lines)

# remove review flags if requested (not recommended!!)
if cli_args.no_review:
    nout_lines = [line for line in buffer.splitlines(True) if "^ TODO" not in line]

with open(cli_args.output_file,"w") as f:
    f.writelines(nout_lines)


print(f"Converted {converted} lines on {len(lines)} total, {instructions} instruction lines")
print(f"Converted instruction ratio {converted}/{instructions} {int(100*converted/instructions)}%")
if unknown_instructions:
    print(f"Unknown instructions: ")
    for s in sorted(unknown_instructions):
        if "nop" in s:
            print("  unofficial nop")
        else:
            print(f"  {s}")
else:
    print("No unknown instructions")

print("\nPLEASE REVIEW THE CONVERTED CODE CAREFULLY AS IT MAY CONTAIN ERRORS!\n")
print("(some TODO: review lines may have been added, and the code won't build on purpose)")




