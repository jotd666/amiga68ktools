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
# TODO:
##- cmp: add a FIX_CMP_CARRY after each one: INVERT_C + SET_X_FROM_C, maybe optional
## as bcs/bcc inversion is way faster and if beq/bne it is not immediately useful
##- cmp + bmi??
##- review: sec/clc + dex/dec + adc/sbc sandwich
##- review: php+sei
##- optim: grouping of simple shifts from 68k code

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



single_instructions = {"nop":"nop",
"rts":"rts",
"txs":"illegal   <-- TODO: unsupported transfer to stack register",
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
"pha":f"movem.w\t{registers['a']},-(sp)",  # movem preserves CCR like original 6502 inst.
"pla":f"movem.w\t(sp)+,{registers['a']}",  # it takes more cycles but who cares?
"php":"PUSH_SR",
"plp":"POP_SR",
"lsr":f"lsr\t#1,{registers['a']}",   # for code that doesn't use "A" parameter for shift ops
"asl":f"asl\t#1,{registers['a']}",
"ror":f"roxr\t#1,{registers['a']}",
"rol":f"roxl\t#1,{registers['a']}",
"sec":"SET_XC_FLAGS",
"clc":"CLR_XC_FLAGS",
"sec":"SET_XC_FLAGS",
"clc":"CLR_XC_FLAGS",
"sei":"SET_I_FLAG",
"cli":"CLR_I_FLAG",
"sed":"illegal   <-- TODO: unsupported set decimal mode",
"cld":"nop",
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
    return generic_logical_op("tst",args,comment).replace(f",{registers['a']}","")


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
                    return f"""\tGET_ADDRESS_Y\t{arg}{comment}
\t{inst}\t#1,({registers['awork1']},{index_reg}.w){out_comment} [...]"""
                else:
                    # X indirect indexed
                    arg = arg.strip("(")
                    arg2 = index_reg
                    if arg2.lower() != 'd1':
                        # can't happen
                        raise Exception("Unsupported indexed mode {}!=d1: {} {}".format(arg2,inst," ".join(args)))

                    return f"""\tGET_ADDRESS_X\t{arg}{comment}
\t{inst}\t#1,({registers['awork1']}){out_comment} [...]"""
            else:
                # X/Y indexed direct
                return f"""\tGET_ADDRESS\t{arg}{comment}
\t{inst}\t#1,({registers['awork1']},{index_reg}.w){out_comment} [...]"""
           # various optims

        return f"""\tGET_ADDRESS\t{arg}{comment}
\t{inst}\t#1,({registers['awork1']}){out_comment} [...]"""

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

    return f"""\tGET_ADDRESS\t{arg}{comment}
\t{inst}\t({registers['awork1']}),{regdst}{out_comment} [...]"""
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
                return f"""\tGET_ADDRESS_Y\t{arg}{comment}
\t{inst}\t{regsrc},({registers['awork1']},{index_reg}.w){out_comment} [...]"""

            else:
                # X indirect indexed
                arg = arg.strip("(")
                arg2 = index_reg
                if arg2.lower() != 'd1':
                    # can't happen
                    raise Exception("Unsupported indexed mode {}!=d1: {} {}".format(arg2,inst," ".join(args)))

                return f"""\tGET_ADDRESS_X\t{arg}{comment}
    {inst}\t{regsrc},({registers['awork1']}){out_comment} [...]"""
        else:
            # X/Y indexed direct
            return f"""\tGET_ADDRESS\t{arg}{comment}
    {inst}\t{regsrc},({registers['awork1']},{index_reg}.w){out_comment} [...]"""

    return f"""\tGET_ADDRESS\t{arg}{comment}
\t{inst}\t{regsrc},({registers['awork1']}){out_comment} [...]"""

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
                return f"""\tGET_ADDRESS_Y\t{arg}{comment}
\t{inst}\t({registers['awork1']},{index_reg}.w),{regdst}{out_comment} [...]"""
            else:
                # X indirect indexed
                arg = arg.strip("(")
                arg2 = index_reg
                if arg2.lower() != 'd1':
                    # can't happen
                    raise Exception("Unsupported indexed mode {}!=d1: {} {}".format(arg2,inst," ".join(args)))

                return f"""\tGET_ADDRESS_X\t{arg}{comment}
\t{inst}\t({registers['awork1']}),{regdst}{out_comment} [...]"""
        else:
            # X/Y indexed direct
            return f"""\tGET_ADDRESS\t{arg}{comment}
\t{inst}\t({registers['awork1']},{index_reg}.w),{regdst}{out_comment} [...]"""
       # various optims
    else:
        if arg[0]=='#':
            # various optims for immediate mode
            if inst=="move.b":
                val = parse_hex(arg[1:],"WTF")
                if val == 0:
                    # move 0 => clr
                    return f"\tclr.b\t{regdst}{comment}"
                elif val == 0xff:
                    # move ff => st
                    return f"\tst.b\t{regdst}{comment}"
            elif inst=="eor.b" and parse_hex(arg[1:])==0xff:
                # eor ff => not
                return f"\tnot.b\t{regdst}{comment}"

            return f"\t{inst}\t{arg},{regdst}{comment}"

    return f"""\tGET_ADDRESS\t{arg}{comment}
\t{inst}\t({registers['awork1']}),{regdst}{out_comment} [...]"""




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
    # bcc/bmi/etc work the other way round but if we just invert there"s a problem
    # when operands are equal... So better convert as is and then post process

    p = args[0]
    if p[0]=='#':
        if parse_hex(p[1:],"WTF")==0:
            # optim
            out = f"\ttst.b\t{registers[reg]}{comment}"
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
carry_generating_instructions = {"lsr.b","asl.b","roxr.b","roxl.b","subx.b","addx.b"}

# post-processing phase is crucial here, as the converted code is guaranteed to be WRONG
# as opposed to Z80 conversion where it could be optimizations or warnings about well-known
# problematic constructs

for i,line in enumerate(nout_lines):
    line = line.rstrip()
    toks = line.split("|",maxsplit=1)
    if len(toks)==2:
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
                if prev_fp == clrxcflags_inst:
                    nout_lines[i-1] = f"{out_start_line_comment} clc+bcc => bra\n"
                    nout_lines[i] = nout_lines[i].replace("\t"+finst,"\tbra.b")
                elif prev_fp[0] == "cmp.b":
                    # we KNOW we generated it wrong as in 6502 conditions are opposed. Change to bcs
                    nout_lines[i] = f"\t{out_start_line_comment} bcc=>bcs\n"+nout_lines[i].replace("\tbcc","\tbcs")
                elif prev_fp[0] not in carry_generating_instructions:
                    if not follows_sr_protected_block(nout_lines,i):
                        nout_lines[i] += f"         ^^^^^^ TODO: warning: stray bcc test\n"

        elif finst == "bcs":
            # if previous instruction sets X flag properly, don't bother, but rol/ror do not!!
            if prev_fp:
                if prev_fp == setxcflags_inst:
                    nout_lines[i-1] = f"{out_start_line_comment} sec+bcs => bra\n"
                    nout_lines[i] = nout_lines[i].replace(finst,"bra.b")
                elif prev_fp[0] == "cmp.b":
                    # we KNOW we generated it wrong as in 6502 conditions are opposed. Change to bcs
                    nout_lines[i] = f"\t{out_start_line_comment} bcs=>bcc\n"+nout_lines[i].replace("\tbcs","\tbcc")
                elif prev_fp[0] not in carry_generating_instructions:
                   if not follows_sr_protected_block(nout_lines,i):
                        nout_lines[i] += f"         ^^^^^^ TODO: warning: review stray bcs test\n"
        elif finst == "rts":
            # if previous instruction sets X flag properly, don't bother, but rol/ror do not!!
            if prev_fp:
                if prev_fp == ["movem.w","d0,-(sp)"]:
                    nout_lines[i] += "          ^^^^^^ TODO: review push to stack+return\n"
                elif prev_fp[0] == "cmp.b":
                    nout_lines[i] += "          ^^^^^^ TODO: review stray cmp (check caller)\n"

        elif finst == "addx.b":
            if prev_fp == clrxcflags_inst:
                # clc+adc => add (way simpler & faster)
                nout_lines[i-1] = nout_lines[i-1].replace(clrxcflags_inst[0],"")
                nout_lines[i] = nout_lines[i].replace("addx.b","add.b")
        elif finst == "subx.b":
            if prev_fp == setxcflags_inst:
                # clc+adc => add (way simpler & faster)
                nout_lines[i-1] = nout_lines[i-1].replace(setxcflags_inst[0],"")
                nout_lines[i] = nout_lines[i].replace("subx.b","sub.b")
        elif finst not in ["bne","beq"] and prev_fp and prev_fp[0] == "cmp.b":
                nout_lines[i] = "          ^^^^^^ TODO: review stray cmp (insert SET_X_FROM_CLEARED_C)\n"+nout_lines[i]

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
        if tok == "eor" and "(" in toks[1]:
            # 68k can't handle such modes
            comment = "\t|"+line.split("|")[1]
            first_param,second_param = split_params(toks[1])
            nout_lines_2.append(f"\tmove.b\t{first_param},{tmpreg}{comment}\n")
            nout_lines_2.append(line.replace(first_param,tmpreg)+"\n")
            continue
        if tok in {"roxr","roxl","ror","rol","lsr","asl"} and "(" in toks[1]:
            # 68k can't handle such modes
            comment = "\t|"+line.split("|")[1]
            first_param,second_param = split_params(toks[1])
            nout_lines_2.append(f"\tmove.b\t{second_param},{tmpreg}{comment}\n")
            nout_lines_2.append(line.replace(second_param,tmpreg)+"\n")
            nout_lines_2.append("\tPUSH_SR\n")
            nout_lines_2.append(f"\tmove.b\t{tmpreg},{second_param}{comment}\n")
            nout_lines_2.append("\tPOP_SR\n")
            continue
        elif tok in {"addx","subx"}:
            comment = "\t|"+line.split("|")[1]
            first_param,second_param = split_params(toks[1])
            if "(" in first_param or '#' in first_param:
                # 68k can't handle such modes
                nout_lines_2.append(f"\tmove.b\t{first_param},{tmpreg}{comment}\n")
                nout_lines_2.append(line.replace(first_param,tmpreg)+"\n")
                continue


    nout_lines_2.append(line+"\n")

nout_lines = []
# ultimate pass to remove useless POP+PUSH SR
prev_line = ""
for line in nout_lines_2:
    if "POP_SR" in prev_line and "PUSH_SR" in line:
        nout_lines.pop()
        continue
    nout_lines.append(line)
    prev_line = line

if cli_args.spaces:
    nout_lines = [tab2space(n) for n in nout_lines]


f = io.StringIO()

if True:
    X = registers['x']
    Y = registers['y']
    C = registers['c']
    V = registers['v']
    A = registers['a']
    W = registers['dwork1']
    f.write(f"""{out_start_line_comment} Converted with 6502to68k by JOTD
{out_start_line_comment}
{out_start_line_comment} make sure you call "cpu_init" first so bits 8-15 of data registers
{out_start_line_comment} are zeroed out so we can use (ax,dy.w) addressing mode
{out_start_line_comment} without systematic masking
{out_start_line_comment}
{out_start_line_comment} WARNING: you also have to add clr.w {registers['x']} and clr.w {registers['y']}
{out_start_line_comment} at start of any interrupt you could hook
{out_start_line_comment} we don't want to mask those at each X,Y indexed instruction
{out_start_line_comment} for performance reasons

""")

    if cli_args.output_mode == "mit":
        f.write(f"""
\t.macro\tSBC_X\taddress
\tINVERT_XC_FLAGS
\tGET_ADDRESS\t\\address
\tmove.b\t({registers['awork1']},{X}.w),{W}
\tsubx.b\t{W},{A}
\tINVERT_XC_FLAGS
\t.endm
\t
\t.macro\tSBC_Y\taddress
\tINVERT_XC_FLAGS
\tGET_ADDRESS\t\\address
\tmove.b\t({registers['awork1']},{Y}.w),{W}
\tsubx.b\t{W},{A}
\tINVERT_XC_FLAGS
\t.endm
\t
\t.macro\tSBC\taddress
\tINVERT_XC_FLAGS
\tGET_ADDRESS\t\\address
\tmove.b\t({registers['awork1']}),{W}
\tsubx.b\t{W},{A}
\tINVERT_XC_FLAGS
\t.endm
\t
\t.macro\tSBC_IMM\tparam
\tINVERT_XC_FLAGS
\tmove.b\t#\param,{W}
\tsubx.b\t{W},{A}
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
\tbeq.b\t0f
\tbclr\t#4,{registers['dwork1']}   | C is set: clear X
0:
\tmove.w\t{registers['dwork1']},(sp)
\tPOP_SR
\t.endm

.macro CLR_XC_FLAGS
\tmoveq\t#0,{C}
\troxl.b\t#1,{C}
\t.endm
\t.macro SET_XC_FLAGS
\tst\t{C}
\troxl.b\t#1,{C}
\t.endm

\t.macro CLR_V_FLAG
\tmoveq\t#0,{V}
\tadd.b\t{V},{V}
\t.endm

\t.macro SET_I_FLAG
^^^^ TODO: insert interrupt disable code here
\t.endm
\t.macro CLR_I_FLAG
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

\t.macro READ_LE_WORD\tsrcreg
\tPUSH_SR
\tmove.b\t(1,\srcreg),{registers['dwork1']}
\tlsl.w\t#8,{registers['dwork1']}
\tmove.b\t(\srcreg),{registers['dwork1']}
\tmove.w\t{registers['dwork1']},\srcreg
\tPOP_SR
\t.endm

\t.macro GET_ADDRESS\toffset
\tlea\t\offset,{registers['awork1']}
\tjbsr\tget_address
\t.endm

\t.macro GET_ADDRESS_X\toffset
\tlea\t\offset,{registers['awork1']}
\tjbsr\tget_address
\tlea\t({registers['awork1']},{registers['x']}.w),{registers['awork1']}
\tREAD_LE_WORD\t{registers['awork1']}
\tjbsr\tget_address
\t.endm

\t.macro GET_ADDRESS_Y\toffset
\tGET_ADDRESS\t\\offset
\tREAD_LE_WORD\t{registers['awork1']}
\tjbsr\tget_address
\t.endm


""")
    else:
        f.write(f"""\tCLR_XC_FLAGS:MACRO
\tmoveq\t#0,{C}
\troxl.b\t#1,{C}
\tENDM
\tSET_XC_FLAGS:MACRO
\tst.b\t{C}
\troxl.b\t#1,{C}
\tENDM

\tCLR_V_FLAG:MACRO
\tmoveq\t#0,{V}
\tadd.b\t{V},{V}
\tENDM

\tSET_I_FLAG:MACRO
^^^^ TODO: insert interrupt disable code here
\tENDM
\tCLR_I_FLAG:MACRO
^^^^ TODO: insert interrupt enable code here
\tENDM
""")

    f.write("cpu_init:\n")
    for i in range(8):
        f.write(f"\tmoveq\t#0,d{i}\n")
    f.write("\trts\n\n")

    f.write(f"""get_address:
        ^^^^ TODO: implement this by adding memory base to {registers['awork1']}
\trts

""")


buffer = f.getvalue()+"".join(nout_lines)

# remove review flags if requested (not recommended!!)
if cli_args.no_review:
    nout_lines = [line for line in buffer.splitlines(True) if "^ TODO" not in line]
else:
    nout_lines = [line for line in buffer.splitlines(True)]

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




