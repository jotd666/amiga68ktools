#TODO: optimize beq (not .b) etc... by jxx if mit syntax
# also if mit jmp => jra
#

#
# you'll have to implement the macro GET_ADDRESS_BASE to return pointer on memory layout
# to replace lea/move/... in memory
# extract RAM memory constants as defines, not variables
# work like an emulator
#
# this is completely different from Z80. Easier for registers, but harder
# for memory because of those indirect indexed modes that read pointers from memory
# so we can't really map 32-bit model on original code without heavily adapting everything
#
# on Z80, the ld instruction acted like lea or move, and it was easier to keep separate address
# space for RAM and ROM.
#
# note: the "mot" mode is outdated (macros are obsolete or missing)
#
# TODO:
##- cmp: add a FIX_CMP_CARRY after each one: INVERT_C + SET_X_FROM_C, maybe optional
## as bcs/bcc inversion is way faster and if beq/bne it is not immediately useful
##- cmp + bmi??
##- review: sec/clc + dex/dec + adc/sbc sandwich
##- review: php+sei
##- optim: grouping of simple shifts from 68k code
##- check cmp followed by roxr or addx/subx
##- review: sbc/adc after cmp without prior sec/clc/add/sub

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
parser.add_argument("output_include_file")

cli_args = parser.parse_args()

no_mame_prefixes = cli_args.no_mame_prefixes

if os.path.abspath(cli_args.input_file) == os.path.abspath(cli_args.output_file):
    raise Exception("Define an output file which isn't the input file")

if cli_args.input_mode == "mit":
    in_comment = "|"
    in_start_line_comment = "*"
    in_hex_sign = "0x"
    branch_letter = "j"
else:
    in_comment = ";"
    in_start_line_comment = in_comment
    in_hex_sign = "$"
    branch_letter = "b"

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

def split_params(params):
    nb_paren = 0
    rval = []
    cur = []
    for c in params:
        if c=='(':
            nb_paren += 1
        elif c==')':
            nb_paren -= 1
        elif c==',' and nb_paren==0:
            # new param
            rval.append("".join(cur))
            cur.clear()
            continue
        cur.append(c)

    rval.append("".join(cur))
    return rval

def change_tst_to_btst(nout_lines,i):
    nout_lines[i-1] = nout_lines[i-1].replace("tst.b\t","btst.b\t#6,")
    nout_lines[i] = (nout_lines[i].replace("bvc\t","beq\t",1).replace("bvs\t","bne\t",1)
    + "          ^^^^^^ TODO: check bit 6 of operand\n")

address_re = re.compile("^([0-9A-F]{4}):")
label_re = re.compile("^(\w+):")
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
                if no_mame_prefixes:
                    if label_re.match(line) and not line.strip().endswith(":"):
                        # label + instruction: split line
                        loclines = line.split(":",maxsplit=1)
                        lines.append((loclines[0]+":",False,i*0x10))
                        line = loclines[1]   # rest of line

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
"a":"d0","x":"d1","y":"d2","p":"sr","c":"d7","v":"d3",
"dwork1":"d4","dwork2":"d5","dwork3":"d6",
"awork1":"a0"}
inv_registers = {v:k.upper() for k,v in registers.items()}

X = registers['x']
Y = registers['y']
C = registers['c']
V = registers['v']
A = registers['a']
W = registers['dwork1']
AW = registers['awork1']
AW_PAREN = f"({AW})"

single_instructions = {"nop":"nop",  # no need to convert to no-operation
"rts":"rts",
#"txs":'TXS',
"txs":'nop',
"tsx":'ERROR   "unsupported transfer from stack register"',
"txa":f"move.b\t{X},{A}",
"tya":f"move.b\t{Y},{A}",
"tax":f"move.b\t{A},{X}",
"tay":f"move.b\t{A},{Y}",
"dex":f"subq.b\t#1,{X}",
"dey":f"subq.b\t#1,{Y}",
"dec":f"subq.b\t#1,{A}",
"inx":f"addq.b\t#1,{X}",
"iny":f"addq.b\t#1,{Y}",
"inc":f"addq.b\t#1,{A}",
"pha":f"movem.w\t{A},-(sp)",  # movem preserves CCR like original 6502 inst.
"pla":f"move.w\t(sp)+,{A}",  # move not movem as pla sets N and Z
"php":"PUSH_SR",
"plp":"POP_SR",
"lsr":f"lsr\t#1,{A}",   # for code that doesn't use "A" parameter for shift ops
"asl":f"asl\t#1,{A}",
"ror":f"roxr\t#1,{A}",
"rol":f"roxl\t#1,{A}",
"rti":'ERROR  "unsupported return from interrupt!"',
"sec":"SET_XC_FLAGS",
"clc":"CLR_XC_FLAGS",
"sei":"SET_I_FLAG",
"cli":"CLR_I_FLAG",
"sed":'ERROR  "TODO: unsupported set decimal mode"',
"cld": "nop",
"clv":f"CLR_V_FLAG",
}

m68_regs = set(registers.values())


lab_prefix = "l_"

def add_entrypoint(address):
    addresses_to_reference.add(address)

def parse_hex(s,default=None):
    is_hex = s.startswith(("$","0x"))
    s = s.strip("$")
    try:
        return int(s,16 if is_hex else 10)
    except ValueError as e:
        if s.startswith("%"):
            return int(s[1:],2)
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
    # hack
    return generic_logical_op("BIT",args,comment).replace(f",{A}","")


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
    return "\tPUSH_SR\n{}\n\tPOP_SR".format(generic_indexed_to("move",src,args,comment))

def generic_shift_op(inst,args,comment):
    arg = args[0]
    inst += ".b"
    if arg==registers['a']:
        return f"\t{inst}\t#1,{arg}{comment}"
    else:
        y_indexed = False

        if len(args)>1:
            # register indexed. There are many modes!
            index_reg = args[1].strip(")")
            if arg.startswith("("):
                if arg.endswith(")"):
                    # Y indirect indexed
                    arg = arg.strip("()")
                    return f"""\tGET_INDIRECT_ADDRESS\t{arg}{comment}
\t{inst}\t#1,({AW},{index_reg}.w){out_comment} [...]"""
                else:
                    # X indirect indexed
                    arg = arg.strip("(")
                    arg2 = index_reg
                    if arg2.lower() != 'd1':
                        # can't happen
                        raise Exception("Unsupported indexed mode {}!=d1: {} {}".format(arg2,inst," ".join(args)))

                    return f"""\tGET_ADDRESS_X\t{arg}{comment}
\t{inst}\t#1,({AW}){out_comment} [...]"""
            else:
                # X/Y indexed direct
                return f"""\tGET_ADDRESS\t{arg}{comment}
\t{inst}\t#1,({AW},{index_reg}.w){out_comment} [...]"""
           # various optims

        return f"""\tGET_ADDRESS\t{arg}{comment}
\t{inst}\t#1,({AW}){out_comment} [...]"""

def generic_logical_op(inst,args,comment):
    return generic_indexed_from(inst,'a',args,comment)

def f_lsr(args,comment):
    return generic_shift_op("lsr",args,comment)
def f_asl(args,comment):
    return generic_shift_op("asl",args,comment)
def f_ror(args,comment):
    return generic_shift_op("roxr",args,comment)
def f_rol(args,comment):
    return generic_shift_op("roxl",args,comment)
def f_ora(args,comment):
    return generic_logical_op("or",args,comment)
def f_and(args,comment):
    return generic_logical_op("and",args,comment)
def f_eor(args,comment):
    return generic_logical_op("eor",args,comment)

def f_adc(args,comment):
    return generic_indexed_from("addx",'a',args,comment)
def f_sbc(args,comment):
    dest = 'a'
    arg = args[0]
    y_indexed = False
    regdst = registers[dest]
    if len(args)>1:
        # register indexed. There are many modes!
        index_reg = args[1].strip(")")
        if arg.startswith("("):
            if arg.endswith(")"):
                # Y indirect indexed
                arg = arg.strip("()")
                return f"""\tSBC_IND_Y\t{arg}{comment}"""
            else:
                # X indirect indexed
                arg = arg.strip("(")
                arg2 = index_reg

                return f"""\tSBC_X_IND\t{arg}{comment}"""
        else:
            # X/Y indexed direct
            return f"""\tSBC_{inv_registers[index_reg]}\t{arg}{comment}"""
       # various optims
    else:
        if arg[0]=='#':
            # immediate mode
            return f"\tSBC_IMM\t{arg[1:]}{comment}"

    return f"\tSBC\t{arg}{comment}"


def generic_indexed_to(inst,src,args,comment):
    arg = args[0]
    if inst.islower():
        inst += ".b"
    y_indexed = False
    regsrc = registers.get(src,src)
    if len(args)>1:
        # register indexed. There are many modes!
        index_reg = args[1].strip(")")
        if arg.startswith("("):
            if arg.endswith(")"):
                # Y indirect indexed
                arg = arg.strip("()")
                return f"""\tGET_INDIRECT_ADDRESS\t{arg}{comment}
\t{inst}\t{regsrc},({AW},{index_reg}.w){out_comment} [...]"""

            else:
                # X indirect indexed
                arg = arg.strip("(")
                arg2 = index_reg
                if arg2.lower() != 'd1':
                    # can't happen
                    raise Exception("Unsupported indexed mode {}!=d1: {} {}".format(arg2,inst," ".join(args)))

                return f"""\tGET_ADDRESS_X\t{arg}{comment}
    {inst}\t{regsrc},({AW}){out_comment} [...]"""
        else:
            # X/Y indexed direct
            return f"""\tGET_ADDRESS\t{arg}{comment}
    {inst}\t{regsrc},({AW},{index_reg}.w){out_comment} [...]"""

    return f"""\tGET_ADDRESS\t{arg}{comment}
\t{inst}\t{regsrc},({AW}){out_comment} [...]"""

def generic_indexed_from(inst,dest,args,comment):
    arg = args[0]
    if inst.islower():
        inst += ".b"
    y_indexed = False
    regdst = registers[dest]
    if len(args)>1:
        # register indexed. There are many modes!
        index_reg = args[1].strip(")")
        if arg.startswith("("):
            if arg.endswith(")"):
                # Y indirect indexed
                arg = arg.strip("()")
                return f"""\tGET_INDIRECT_ADDRESS\t{arg}{comment}
\t{inst}\t({AW},{index_reg}.w),{regdst}{out_comment} [...]"""
            else:
                # X indirect indexed
                arg = arg.strip("(")
                arg2 = index_reg
                if arg2.lower() != 'd1':
                    # can't happen
                    raise Exception("Unsupported indexed mode {}!=d1: {} {}".format(arg2,inst," ".join(args)))

                return f"""\tGET_ADDRESS_X\t{arg}{comment}
\t{inst}\t({AW}),{regdst}{out_comment} [...]"""
        else:
            # X/Y indexed direct
            return f"""\tGET_ADDRESS\t{arg}{comment}
\t{inst}\t({AW},{index_reg}.w),{regdst}{out_comment} [...]"""
       # various optims
    else:
        if arg[0]=='#':
            # various optims for immediate mode
            if inst=="move.b":
                val = parse_hex(arg[1:],"WTF")
                if val == 0:
                    # move 0 => clr
                    return f"\tclr.b\t{regdst}{comment}"
# replacing lda #0xFF by st.b d0 usually works except that Z,N flags aren't set!
##                elif val == 0xff:
##                    # move ff => st
##                    return f"\tst.b\t{regdst}{comment}"
            elif inst=="eor.b" and parse_hex(arg[1:])==0xff:
                # eor ff => not
                return f"\tnot.b\t{regdst}{comment}"

            return f"\t{inst}\t{arg},{regdst}{comment}"

    return f"""\tGET_ADDRESS\t{arg}{comment}
\t{inst}\t({AW}),{regdst}{out_comment} [...]"""




def f_jmp(args,comment):
    target_address = None
    arg = args[0]
    label = arg2label(arg)
    if arg != label:
        # had to convert the address, keep original to reference it
        target_address = arg

    out = ""
    if "(" in arg:
        # indirect jump: not supported direct: note the error
        out = '\tERROR\t"indirect jmp"\n'
    out += f"\tjmp\t{label}{comment}"

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
    # bcc/bmi/etc work the other way round but if we just invert there"s a problem
    # when operands are equal... So better convert as is and then post process

    p = args[0]
    if p[0]=='#':
        if parse_hex(p[1:],"WTF")==0:
            # optim but warn, as cmp #0 is suspicious in 6502: most instructions
            # already set the NZ flags
            out = '\tERROR   "replacing by tst.b but check if carry is required"\n'
            out += f"\ttst.b\t{registers[reg]}{comment}"
        else:
            out = f"\tcmp.b\t{p},{registers[reg]}{comment}"
    else:
        out = generic_indexed_from("cmp",reg,args,comment)
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

    if "(" in func:
        # indirect jsr: not supported direct: note the error
        out = '\tERROR\t"indirect jsr"\n'

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

    out += f"\t{branch_letter}{cond}\t{func}{comment}"

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
                if inst.startswith("."):
                    # as-is
                    out = l
                else:
                    out = f"{l}\n   ^^^^ TODO: unknown/unsupported instruction {inst}"
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
# this is more difficult than in Z80 because some instructions need 2 lines (one
# to get address and one for the operation) so it was causing more problems that it solved
##for v in [list(v) for k,v in itertools.groupby(enumerate(out_lines),lambda x:x[1].split(out_comment)[0])]:
##    repeats = len(v)
##    if repeats>1:
##        # we have a group
##        line,instr = v[0]
##        if "#1," in instr:
##            grouped = instr.rstrip().replace("#1,",f"#{len(v)},")
##            grouped += f" * {len(v)}\n"
##            out_lines[line] = grouped
##            # delete following lines
##            for i in range(line+1,line+len(v)):
##                out_lines[i] = ""



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
        if cli_args.output_mode == "mit":
            line = line.replace(".db","\t.byte")
            line = line.replace("$","0x")
        else:
            line = line.replace(".db","\tdc.b")
        line = line.replace(in_comment,out_comment)
    elif line.startswith(".dw") and line[3].isspace():
        if cli_args.output_mode == "mit":
            line = line.replace(".dw","\t.long")
            line = line.replace("$","0x")
        else:
            line = line.replace(".dw","\tdc.w")
        line = line.replace(in_comment,out_comment)

    # also fix .byte,
    line = line.replace(".byte,",".byte\t")

    nout_lines.append(line+"\n")

def replace_sub_instruction(finst,ninst,line):
    toks = line.split(out_comment)
    args = toks[0].split()
    if finst == "SBC_IMM":
        # we have to re-parse, remove macro

        return f"\t{ninst}\t#{args[1]},{A}\t{out_comment}{toks[1]}"
    else:
        return f"\t{ninst}\t{args[1]}{out_comment}\t{toks[1]}"


def find_sed_line(lines,start):
    for i in range(start,0,-1):
        toks = lines[i].split()
        if toks:
            if "rts" in toks or "jmp" in toks:
                return None
            if "sed]" in toks:
                return i
    return None

def remove_instruction(line):
    comment_pos = line.index(out_comment)
    return " "*comment_pos + line[comment_pos:]

def follows_sr_protected_block(nout_lines,i):
    # we have a chance of protected block only if POP_SR
    # was just before the branch test
    if "POP_SR" not in nout_lines[i-1]:
        return False

    for j in range(i-2,1,-1):
        line = nout_lines[j]
        if line.startswith("\trts"):
            # sequence break:
                return False

        if line.startswith("\tPUSH_SR"):
            # encountered POP then PUSH while going back
            finst = nout_lines[j-1].split()[0]
            return finst in carry_generating_instructions

    return True

# add review flag message in case of move.x followed by a branch
# also add review for writes to unlabelled memory
# also post-optimize stuff
prev_fp = None

reg_a = registers["a"]
clrxcflags_inst = ["CLR_XC_FLAGS"]
setxcflags_inst = ["SET_XC_FLAGS"]

# sub/add aren't included as they're the translation of dec/inc which don't affect C
carry_generating_instructions = {"lsr.b","asl.b","roxr.b","roxl.b","subx.b","addx.b","SBC_IMM","SBC","SBC_X","SBC_Y"}
conditional_branch_instructions = {"bpl","bmi","bls","bne","beq","bhi","blo","bcc","bcs","blt","ble","bge","bgt"}
conditional_branch_instructions.update({f"j{x[1:]}" for x in conditional_branch_instructions})

grouping = True
# group several same instructions like add, lsr... #1 in one go
if grouping:
    # after generation, a lot of instructions can be condensed, specially all INC, ROR, ...
    prev_toks = None
    last_line = 0
    count = 0
    for i,line in enumerate(nout_lines):
        line = line.rstrip()
        sequence_break = True
        toks = None
        if line and line[0].isspace():
            sequence_break = False
            toks = line.split()[0:2]  # lose offset
            if toks == prev_toks and len(toks)==2:
                arg = toks[1].split(",")
                if len(arg)==2 and arg[0] == "#1":
                    # xxx.b #1,dest we can group that
                    count += 1
                else:
                    sequence_break = True
            else:
                sequence_break = True

        if sequence_break and count:
            for c in range(count):
                ltr = last_line-c-1
                # remove previous same instructions
                nout_lines[ltr] = remove_instruction(nout_lines[ltr])
                # group
            nout_lines[last_line] = nout_lines[last_line].replace("#1,",f"#{count+1},")
            # reset sequence
            count = 0
        prev_toks = toks
        last_line = i

# post-processing phase is crucial here, as the converted code is guaranteed to be WRONG
# as opposed to Z80 conversion where it could be optimizations or warnings about well-known
# problematic constructs

for i,line in enumerate(nout_lines):
    line = line.rstrip()
    toks = line.split("|",maxsplit=1)
    if len(toks)==2 and toks[0].strip():
        fp = toks[0].rstrip().split()
        finst = fp[0]

        if finst == "bvc":
            if prev_fp:
                if prev_fp == ["CLR_V_FLAG"]:
                    nout_lines[i-1] = f"{out_start_line_comment} clv+bvc => jra\n"
                    nout_lines[i] = nout_lines[i].replace(finst,"jra")
                elif prev_fp[0] == "tst.b":
                    change_tst_to_btst(nout_lines,i)
            else:
                nout_lines[i] += "          ^^^^^^ TODO: warning: stray bvc test\n"
        elif finst == "bvs":
            if prev_fp:
                if prev_fp[0] == "tst.b":
                    change_tst_to_btst(nout_lines,i)
            else:
                nout_lines[i] += "          ^^^^^^ TODO: warning: stray bvs test\n"

        elif finst == "bcc":
            # if previous instruction sets X flag properly, don't bother, but rol/ror do not!!
            if prev_fp:
                inst_no_size = prev_fp[0].split(".")[0]

                if prev_fp == clrxcflags_inst:
                    nout_lines[i-1] = f"{out_start_line_comment} clc+bcc => bra\n"
                    nout_lines[i] = nout_lines[i].replace("\t"+finst,"\tbra.b")
                elif prev_fp[0] == "cmp.b":
                    # we KNOW we generated it wrong as in 6502 conditions are opposed. Change to bcs
                    nout_lines[i] = f"\t{out_start_line_comment} bcc=>bcs (cmp above)\n"+nout_lines[i].replace("\tbcc","\tbcs")
                elif prev_fp[0].startswith("b"):  # okay it could be bit but BIT is macroized
                    # there are multiple branch conditions, which means that a cmp could be hidden above
                    if "cmp.b" in nout_lines[i-2]:  # hacky test
                        nout_lines[i] = f"\t{out_start_line_comment} bcc=>bcs (cmp higher above)\n"+nout_lines[i].replace("\tbcc","\tbcs")
                elif prev_fp[0] not in carry_generating_instructions and inst_no_size not in conditional_branch_instructions:
                    if not follows_sr_protected_block(nout_lines,i):
                        nout_lines[i] += '  ERROR  "warning: stray bcc test"\n'

        elif finst == "bcs":
            # if previous instruction sets X flag properly, don't bother, but rol/ror do not!!
            if prev_fp:
                inst_no_size = prev_fp[0].split(".")[0]
                if prev_fp == setxcflags_inst:
                    nout_lines[i-1] = f"{out_start_line_comment} sec+bcs => bra\n"
                    nout_lines[i] = nout_lines[i].replace(finst,"bra.b")
                elif prev_fp[0] == "cmp.b":
                    # we KNOW we generated it wrong as in 6502 conditions are opposed. Change to bcs
                    nout_lines[i] = f"\t{out_start_line_comment} bcs=>bcc\n"+nout_lines[i].replace("\tbcs","\tbcc")
                elif prev_fp[0].startswith("b"):  # okay it could be bit but BIT is macroized
                    # there are multiple branch conditions, which means that a cmp could be hidden above
                    if "cmp.b" in nout_lines[i-2]:  # hacky test
                        nout_lines[i] = f"\t{out_start_line_comment} bcs=>bcc (cmp higher above)\n"+nout_lines[i].replace("\tbcs","\tbcc")
                elif prev_fp[0] not in carry_generating_instructions and inst_no_size not in conditional_branch_instructions:
                   if not follows_sr_protected_block(nout_lines,i):
                        nout_lines[i] += '     ERROR "warning: review stray bcs test"\n'
        elif finst == "rts":
            # if previous instruction sets X flag properly, don't bother, but rol/ror do not!!
            if prev_fp:
                if prev_fp == ["movem.w","d0,-(sp)"]:
                    nout_lines[i] += '          ERROR  "review push to stack+return"\n'
                elif prev_fp[0] == "cmp.b":
                    nout_lines[i] += '          ERROR  "review stray cmp (check caller)"\n'

        elif finst == "addx.b":
            if prev_fp == clrxcflags_inst or clrxcflags_inst[0] in nout_lines[i-2]:
                # clc+adc => add (way simpler & faster)
                # also try to handle previously set "sed" decimal mode
                # we try to find the previous sed instruction
                sed_line = find_sed_line(nout_lines,i-2)
                if sed_line:
                    print(f"detected & removed sed instruction at line {sed_line+1}, turning addx to abcd")
                    # it's actually a abcd operation
                    nout_lines[sed_line] = ""
                    nout_lines[i] = nout_lines[i].replace("addx.b","abcd")
                else:
                    nout_lines[i-1] = nout_lines[i-1].replace(clrxcflags_inst[0],"")
                    nout_lines[i] = nout_lines[i].replace("addx.b","add.b")
        elif finst in ["subx.b","SBC_IMM"]:
            if prev_fp == setxcflags_inst or setxcflags_inst[0] in nout_lines[i-2]:
                # clc+sbc => sub (way simpler & faster) but careful: if carry is tested afterwards it
                # will be the opposite!
                # also try to handle previously set "sed" decimal mode
                # we try to find the previous sed instruction
                sed_line = find_sed_line(nout_lines,i-2)
                if sed_line:
                    print(f"detected & removed sed instruction at line {sed_line+1}, turning subx to sbcd")
                    nout_lines[sed_line] = ""
                    nout_lines[i] = replace_sub_instruction(finst,"sbcd",nout_lines[i])
                else:
                    nout_lines[i-1] = nout_lines[i-1].replace(setxcflags_inst[0],"")
                    nout_lines[i] = replace_sub_instruction(finst,"sub.b",nout_lines[i])
                # check if next line is bcc/bcs
                nlt = nout_lines[i+1].split(out_comment)[0].split()
                if nlt and nlt[0] in ["bcc","bcs"]:
                    # we have to insert carry inverse flag like SBC does
                    nout_lines[i+1] = "\tINVERT_XC_FLAGS\n"+nout_lines[i+1]

        elif finst not in ["bne","beq","bmi"] and prev_fp and prev_fp[0] == "cmp.b":
                nout_lines[i] = '      ERROR  "review stray cmp (insert SET_X_FROM_CLEARED_C)"\n'+nout_lines[i]

        prev_fp = fp
# post-processing

# the generator assumed that rol, ror... a lot of operations can work directly on non-data registers
# for simplicity's sake, now we post-process the generator to insert read to reg/op with reg/write to mem

tmpreg = registers['dwork1']
nout_lines_2 = []
for line in nout_lines:
    line = line.rstrip()
    if line and line[0].isspace():
        toks = line.split()
        tok = toks[0].split(".")[0]
        if tok in ["eor","abcd","sbcd"] and "(" in toks[1]:
            # 68k can't handle such modes
            comment = "\t|"+line.split(out_comment)[1]
            first_param,second_param = split_params(toks[1])
            nout_lines_2.append(f"\tmove.b\t{first_param},{tmpreg}{comment}\n")
            nout_lines_2.append(line.replace(first_param,tmpreg)+"\n")
            continue
        elif tok in {"roxr","roxl","ror","rol","lsr","asl"} and "(" in toks[1]:
            # 68k can't handle such modes
            comment = "\t|"+line.split(out_comment)[1]
            first_param,second_param = split_params(toks[1])
            nout_lines_2.append(f"\tmove.b\t{second_param},{tmpreg}{comment}\n")
            nout_lines_2.append(line.replace(second_param,tmpreg)+"\n")
            nout_lines_2.append("\tPUSH_SR\n")
            nout_lines_2.append(f"\tmove.b\t{tmpreg},{second_param}{comment}\n")
            nout_lines_2.append("\tPOP_SR\n")
            continue
        elif tok in {"addx","subx","abcd","sbcd"}:
            comment = "\t|"+line.split(out_comment)[1]
            first_param,second_param = split_params(toks[1])
            if "(" in first_param or '#' in first_param:
                # 68k can't handle such modes
                nout_lines_2.append(f"\tmove.b\t{first_param},{tmpreg}{comment}\n")
                nout_lines_2.append(line.replace(first_param,tmpreg)+"\n")
                continue


    nout_lines_2.append(line+"\n")

nout_lines = []
# ultimate pass to remove useless POP+PUSH SR but not the ones from
# the original code!
prev_line = ""
for line in nout_lines_2:
    if "POP_SR" in prev_line and "PUSH_SR" in line:
        if "plp" not in prev_line and "php" not in line:  # don't touch original plp/php instructions
            nout_lines.pop()
            continue
    nout_lines.append(line)
    prev_line = line



# last pass: optimization pass for zero page accesses. Zero page is guaranteed to be mapped
# and at start of the address space (else my model fails). ZP is necessary to 6502 operation
# else no pointers...
# the idea is to pack GET_ADDRESS <zp_address> + instruction to a single read/write to (a0) macro
# this pass was not in the previous versions of the converter.

if True:   # can be turned off, code is valid without that
    i = 0

    def change_instruction(code,lines,i):
        line = lines[i]
        toks = line.split(out_comment)
        if len(toks)==2:
            toks[0] = f"\t{code}"
            return f" {out_comment} ".join(toks)
        return line

    while i < len(nout_lines):
        line = nout_lines[i]
        toks = line.split()
        if toks and toks[0] == "GET_ADDRESS":
            value = None
            value_str = toks[1]
            try:
                value = int(value_str,16)
            except ValueError:
                try:
                    value = int(value_str.rsplit("_",1)[-1],16)
                except ValueError:
                    pass
            if value is not None and value < 0x100:
                # GET_ADDRESS in zero page. If we recognize the next instruction
                # there's a way to optimize the access, as it's legal and fast
                next_line = nout_lines[i+1]
                toks = next_line.split(out_comment)[0].split()
                if len(toks)==2:
                    inst,params = toks
                    inst = inst.split(".")[0]
                    subparams = params.split(",")
                    # we discard too complex moves, also moves to temp registers
                    # as they continue with following instructions
                    # move.b  d0,(a0) (or the other way round) is supported. So are other
                    # instructions like cmp, add...
                    if len(subparams)==2:
                        src,dest = subparams
                        if src == AW_PAREN and dest in [X,Y,A]:
                            # read instruction
                            line = change_instruction(f"OP_R_ON_ZP_ADDRESS\t{inst},{value_str},{dest}",nout_lines,i)
                            nout_lines[i+1] = ""
                        elif dest == AW_PAREN and src in [X,Y,A]:
                            # write instruction
                            line = change_instruction(f"OP_W_ON_ZP_ADDRESS\t{inst},{value_str},{src}",nout_lines,i)
                            nout_lines[i+1] = ""
                        elif dest == AW_PAREN and inst in ["addq","subq"]:
                            # write instruction
                            line = change_instruction(f"OP_W_ON_ZP_ADDRESS\t{inst},{value_str},{src}",nout_lines,i)
                            nout_lines[i+1] = ""
        nout_lines[i] = line
        i+=1



if cli_args.spaces:
    nout_lines = [tab2space(n) for n in nout_lines]


f = io.StringIO()
finc = io.StringIO()

if True:
    f.write(f"""{out_start_line_comment} Converted with 6502to68k by JOTD
{out_start_line_comment}
{out_start_line_comment} make sure you call "cpu_init" first so bits 8-15 of data registers
{out_start_line_comment} are zeroed out so we can use (ax,dy.w) addressing mode
{out_start_line_comment} without systematic masking
{out_start_line_comment}
{out_start_line_comment} WARNING: you also have to add clr.w {X} and clr.w {Y}
{out_start_line_comment} at start of any interrupt you could hook
{out_start_line_comment} we don't want to mask those at each X,Y indexed instruction
{out_start_line_comment} for performance reasons

""")

    finc.write(f"""{out_start_line_comment} Generated with 6502to68k by JOTD
{out_start_line_comment}
{out_start_line_comment} include file which contains generic macros
{out_start_line_comment} and also macros that the user must fill/tune

""")

    if cli_args.output_mode == "mit":
        finc.write(f"""
    .macro    ERROR    arg
    .error    "\\arg"     | comment out to disable errors
    .endm

\t.ifdef\tMC68020
* 68020 optimized
\t.macro PUSH_SR
\tmove.w\tccr,-(sp)
\t.endm

\t.macro READ_LE_WORD    srcreg
\tPUSH_SR
\tmoveq    #0,d4
\tmove.w    (\srcreg),d4
\trol.w    #8,d4
* we have to use long else it will
* extend sign for > 0x7FFF and will compute wrong offset
\tmove.l    d4,\srcreg
\tPOP_SR
\t.endm

\t.else
* 68000 compliant
\t.macro PUSH_SR
\tmove.w\tsr,-(sp)
\t.endm

\t.macro READ_LE_WORD    srcreg
\tPUSH_SR
\tmoveq    #0,d4
\tmove.b    (1,\srcreg),d4
\tlsl.w    #8,d4
\tmove.b    (\srcreg),d4
* we have to use long else it will
* extend sign for > 0x7FFF and will compute wrong offset
\tmove.l    d4,\srcreg
\tPOP_SR
\t.endm

\t.endif

\t.macro POP_SR
\tmove.w\t(sp)+,ccr
\t.endm

\t.macro OP_R_ON_ZP_ADDRESS\tinst,offset,reg
\t\\inst\\().b\t(a6,\\offset\\().W),\\reg
\t.endm

\t.macro OP_W_ON_ZP_ADDRESS\tinst,offset,reg
\t\\inst\\().b\t\\reg,(a6,\\offset\\().W)
\t.endm

\t.macro\tSBC_X\taddress
\tINVERT_XC_FLAGS
\tGET_ADDRESS\t\\address
\tmove.b\t({AW},{X}.w),{W}
\tsubx.b\t{W},{A}
\tINVERT_XC_FLAGS
\t.endm
\t
\t.macro\tSBC_Y\taddress
\tINVERT_XC_FLAGS
\tGET_ADDRESS\t\\address
\tmove.b\t({AW},{Y}.w),{W}
\tsubx.b\t{W},{A}
\tINVERT_XC_FLAGS
\t.endm
\t
\t.macro\tSBC_IND_Y\taddress
\tINVERT_XC_FLAGS
\tGET_INDIRECT_ADDRESS\t\\address
\tmove.b\t({AW},{Y}.w),{W}
\tsubx.b\t{W},{A}
\tINVERT_XC_FLAGS
\t.endm
\t
\t.macro\tSBC\taddress
\tINVERT_XC_FLAGS
\tGET_ADDRESS\t\\address
\tmove.b\t({AW}),{W}
\tsubx.b\t{W},{A}
\tINVERT_XC_FLAGS
\t.endm

\t.macro\tSBCD_DIRECT\taddress
\tINVERT_XC_FLAGS
\tGET_ADDRESS\t\\address
\tmove.b\t({AW}),{W}
\tscbd\t{W},{A}
\tINVERT_XC_FLAGS
\t.endm
\t
\t.macro\tSBC_IMM\tparam
\tINVERT_XC_FLAGS
\tmove.b\t#\\param,{W}
\tsubx.b\t{W},{A}
\tINVERT_XC_FLAGS
\t.endm

\t.macro\tSBCD_IMM\tparam
\tINVERT_XC_FLAGS
\tmove.b\t#\\param,{W}
\tsbcd\t{W},{A}
\tINVERT_XC_FLAGS
\t.endm

\t.macro INVERT_XC_FLAGS
\tPUSH_SR
\tmove.w\t(sp),{registers['dwork1']}
\teor.b\t#0x11,{registers['dwork1']}
\tmove.w\t{registers['dwork1']},(sp)
\tPOP_SR
\t.endm

{out_start_line_comment} useful to recall C from X (add then move then bcx)
\t.macro\tSET_C_FROM_X
\tPUSH_SR
\tmove.w\t(sp),{registers['dwork1']}
\tbset\t#0,{registers['dwork1']}   | set C
\tbtst\t#4,{registers['dwork1']}
\tbne.b\t0f
\tbclr\t#0,{registers['dwork1']}   | X is clear: clear C
0:
\tmove.w\t{registers['dwork1']},(sp)
\tPOP_SR
\t.endm

\t.macro\tSET_X_FROM_CLEARED_C
\tPUSH_SR
\tmove.w\t(sp),{registers['dwork1']}
\tbset\t#4,{registers['dwork1']}   | set X
\tbtst\t#0,{registers['dwork1']}
\tbeq.b\tskip\\@
\tbclr\t#4,{registers['dwork1']}   | C is set: clear X
skip\\@:
\tmove.w\t{registers['dwork1']},(sp)
\tPOP_SR
\t.endm


* N and V flag set on bits 7 and 6 is now supported
* remove the end of the macro if the game is not using them (no bmi/bvc tests)
    .macro    BIT    arg
    move.b    {A},{registers['dwork1']}
    and.b    \\arg,{registers['dwork1']}    | zero flag
    PUSH_SR
    move.b    \\arg,{registers['dwork1']}
    move.w    (a7),{registers['dwork2']}
    bclr    #3,{registers['dwork2']}
    tst.b    {registers['dwork1']}
    jpl        pos\\@
    bset    #3,{registers['dwork2']}    | set N
pos\\@:
    bclr    #1,{registers['dwork2']}
    btst.b    #6,{registers['dwork1']}
    jeq        b6\\@
    bset    #1,{registers['dwork2']}    | set V
b6\\@:
    move.w    {registers['dwork2']},(a7)
    POP_SR
    .endm


    .macro CLR_XC_FLAGS
    PUSH_SR
    move.w    (sp),{registers['dwork1']}
    and.b    #0xEE,{registers['dwork1']}        | bit 4 = X, bit 0 = C
    move.w    {registers['dwork1']},(sp)
    POP_SR
    .endm

    .macro SET_XC_FLAGS
    PUSH_SR
    move.w    (sp),{registers['dwork1']}
    or.b    #0x11,{registers['dwork1']}        | bit 4 = X, bit 0 = C
    move.w    {registers['dwork1']},(sp)
    POP_SR
    .endm

    .macro CLR_V_FLAG
    PUSH_SR
    move.w    (sp),{registers['dwork1']}
    and.b    #0xFD,{registers['dwork1']}        | bit 1 = V
    move.w    {registers['dwork1']},(sp)
    POP_SR
    .endm

    .macro SET_V_FLAG
    PUSH_SR
    move.w    (sp),{registers['dwork1']}
    or.b    #0x2,{registers['dwork1']}        | bit 1 = V
    move.w    {registers['dwork1']},(sp)
    POP_SR
    .endm

    .macro    SET_NV_FLAGS
    PUSH_SR
    move.w    (sp),{registers['dwork1']}
    or.b    #0xA,{registers['dwork1']}        | bit 1 = V, bit 3 = N
    move.w    {registers['dwork1']},(sp)
    POP_SR
    .endm

\t.macro TXS
\tERROR "TODO: insert txs handling if needed (or remove)"
\t.endm
\t.macro SET_I_FLAG
\tERROR "TODO: insert interrupt disable code here"
\t.endm
\t.macro CLR_I_FLAG
\tERROR  "TODO: insert interrupt enable code here"
\t.endm




\t.macro GET_ADDRESS\toffset
\tlea\t\offset,{AW}
\tjbsr\tget_address
\t.endm

\t.macro GET_ADDRESS_X\toffset
\t.ifgt\t\\offset-0x8000
\tlea\t\\offset,{AW}
\t.else
\tlea\t\\offset\\().w,a0
\t.endif
\tjbsr\tget_address
\tlea\t({AW},{X}.w),{AW}
\tREAD_LE_WORD\t{AW}
\tjbsr\tget_address
\t.endm

\t.macro GET_INDIRECT_ADDRESS\toffset
\tGET_ADDRESS\t\\offset
\tREAD_LE_WORD\t{AW}
\tjbsr\tget_address
\t.endm


""")
        f.write(f'\t.include\t"{cli_args.output_include_file}"\n')

    else:
        finc.write(f"""SBC_X:MACRO
\tINVERT_XC_FLAGS
\tGET_ADDRESS\t\\1
\tmove.b\t({AW},{X}.w),{W}
\tsubx.b\t{W},{A}
\tINVERT_XC_FLAGS
\tENDM
\t
SBC_Y:MACRO
\tINVERT_XC_FLAGS
\tGET_ADDRESS\t\\1
\tmove.b\t({AW},{Y}.w),{W}
\tsubx.b\t{W},{A}
\tINVERT_XC_FLAGS
\tENDM
\t
SBC:MACRO
\tINVERT_XC_FLAGS
\tGET_ADDRESS\t\\1
\tmove.b\t({AW}),{W}
\tsubx.b\t{W},{A}
\tINVERT_XC_FLAGS
\tENDM
SBCD:MACRO
\tINVERT_XC_FLAGS
\tGET_ADDRESS\t\\1
\tmove.b\t({AW}),{W}
\tsbcd\t{W},{A}
\tINVERT_XC_FLAGS
\tENDM

SBC_IMM:MACRO
\tINVERT_XC_FLAGS
\tmove.b\t#\\1,{W}
\tsubx.b\t{W},{A}
\tINVERT_XC_FLAGS
\tENDM

SBCD_IMM:MACRO
\tINVERT_XC_FLAGS
\tmove.b\t#\\1,{W}
\tsbcd\t{W},{A}
\tINVERT_XC_FLAGS
\tENDM

CLR_XC_FLAGS:MACRO
\tmoveq\t#0,{C}
\troxl.b\t#1,{C}
\tENDM
\tSET_XC_FLAGS:MACRO
\tst.b\t{C}
\troxl.b\t#1,{C}
\tENDM

CLR_V_FLAG:MACRO
\tmoveq\t#0,{V}
\tadd.b\t{V},{V}
\tENDM

SET_I_FLAG:MACRO
\t.error  "TODO: insert interrupt disable code here"
\tENDM

CLR_I_FLAG:MACRO
\tERROR  "TODO: insert interrupt enable code here"
\tENDM

\tIFD\tMC68020
\tPUSH_SR:MACRO
\tmove.w\tccr,-(sp)
\tENDM
\t.else
PUSH_SR:MACRO
\tmove.w\tsr,-(sp)
\tENDM
\tENDC
POP_SR:MACRO
\tmove.w\t(sp)+,ccr
\tENDM

READ_LE_WORD:MACRO
\tPUSH_SR
\tmoveq\t#0,{registers['dwork1']}
\tmove.b\t(1,\\1),{registers['dwork1']}
\tlsl.w\t#8,{registers['dwork1']}
\tmove.b\t(\\1),{registers['dwork1']}
\tmove.l\t{registers['dwork1']},\\1
\tPOP_SR
\tENDM

GET_ADDRESS:MACRO
\tlea\t\\1,{AW}
\tjbsr\tget_address
\tENDM

GET_ADDRESS_X:MACRO
\tlea\t\\1,{AW}
\tjbsr\tget_address
\tlea\t({AW},{X}.w),{AW}
\tREAD_LE_WORD\t{AW}
\tjbsr\tget_address
\tENDM

GET_INDIRECT_ADDRESS:MACRO
\tGET_ADDRESS\t\\1
\tREAD_LE_WORD\t{AW}
\tjbsr\tget_address
\tENDM

get_address:
\tERROR   "TODO: implement this by adding memory base to {AW}"
\trts

""")
        f.write(f'\tinclude\t"{cli_args.output_include_file}"\n')

    f.write("\t.global\tcpu_init\n")
    f.write("cpu_init:\n")
    for i in range(8):
        f.write(f"\tmoveq\t#0,d{i}\n")
    f.write("\trts\n\n")




buffer = f.getvalue()+"".join(nout_lines)

# remove review flags if requested (not recommended!!)
if cli_args.no_review:
    nout_lines = [line for line in buffer.splitlines(True) if ".error" not in line]
else:
    nout_lines = [line for line in buffer.splitlines(True)]

with open(cli_args.output_file,"w") as f:
    f.writelines(nout_lines)

if os.path.exists(cli_args.output_include_file):
    print(f"Keeping existing include file {cli_args.output_include_file}")
else:
    print(f"Generating include file {cli_args.output_include_file}. Adaptations are required")
    with open(cli_args.output_include_file,"w") as f:
        f.write(finc.getvalue())


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
print("(some .error: review lines may have been added, and the code won't build on purpose)")




