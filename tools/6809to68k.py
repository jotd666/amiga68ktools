#
# 6809 to 680x0 converter by JOTD (c) 2025
#
# this code has been used to convert the following games
#
# - Gyruss (coordinate transformation code)
# - Track'N'Field (the whole game)
# - Hyper Sports (the whole game)
#

# post_proc: tst.w + GET_.*ADDRESS => remove tst.w
# set macro MOVE_W for alignment (68000/68020) in post processing if source or dest
# is not a register, detect others .w operands in that case
# cmpd generates cmp.w which is not 68000 friendly

# you'll have to implement the macro GET_ADDRESS_FUNC to return pointer on memory layout
# to replace lea/move/... in memory
# extract RAM memory constants as defines, not variables
# work like an emulator
#
# this is completely different from Z80. Easier for registers, but harder
# for memory because of those indirect indexed modes that read pointers from memory
# so we can't really map 32-bit model on original code without heavily adapting everything
#
# however, if memory is not banked, it is possible to create a full 64k address space
# and almost leave the code live its life. Just insert some video update commands there
# and there when the game changes tiles or other things
#
# track'n'field runs without any manual patches now :)
#
# the converter tries to keep A,B and D updated, the result is sometimes it does things
# that aren't really needed. But it's accurate at least and code runs without need for
# complete RE + debug...
#
# what I'm advising is that after the code works 100%, profile it using MAME trace and scripts
# (there are python scripts that do that in that repository) and concentrate on the 68k code
# in regions where the code is often called, optimize manually, and never re-generate
#
# check how conversion+custom post-processing does an automatic job here:
# https://github.com/jotd666/track_and_field

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
parser.add_argument("-c","--code-output",help="68000 source code output file",required=True)
parser.add_argument("-d","--data-output",help="data output file")
parser.add_argument("-I","--include-output",help="include output file",required=True)
parser.add_argument("input_file")


OPENING_BRACKET = ('(','[')
BRACKETS = "[]()"

cli_args = parser.parse_args()

no_mame_prefixes = cli_args.no_mame_prefixes

if os.path.abspath(cli_args.input_file) == os.path.abspath(cli_args.code_output):
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
    branch_prefix = "j"
else:
    out_comment = ";"
    out_start_line_comment = out_comment
    out_hex_sign = "$"
    out_byte_decl = "dc.b"
    out_long_decl = "dc.l"
    jsr_instruction = "jsr"
    branch_prefix = "b"

continuation_comment = f"{out_comment} [...]"
mask_out_comment = f"{out_comment} [masking out]"
MAKE_D_PREFIX = f"\tMAKE_D\t{continuation_comment}\n"

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

def compose_instruction(inst,regdst):
    if regdst:
        out = f"\n\t{inst}\t({registers['awork1']}),{regdst}{continuation_comment}"
    else:
        out = f"\n\t{inst}\t({registers['awork1']}){continuation_comment}"
    return out




address_re = re.compile("^([0-9A-F]{4}):")
label_re = re.compile("^(\w+):")
error = "ERROR"

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


def issue_warning(msg,newline=False):
    rval =  f'\t{error}\t"review {msg}"'
    if newline:
        rval += "\n"
    return rval

# convention:
# a => d0
# x => d1
# y => d2
# u => d3

registers = {
"a":"d0","b":"d1","x":"d2","y":"d3","u":"d4","s":"d5",
"dwork1":"d6",
"dwork2":"d7",
"awork1":"a0",
#"p":"sr",
"dp_base":"a5",
"":""
}
inv_registers = {v:k.upper() for k,v in registers.items()}
# do NOT define this!!
#registers["d"] = registers["a"]
#inv_registers['d'] = 'd'

single_instructions = {"nop":"nop",
"rts":"rts",
"sex":"SEX",
"daa":"DAA",
"abx":"ABX",
"mul":"jbsr\tmultiply_ab",
"nega":f"neg.b\t{registers['a']}",
"negb":f"neg.b\t{registers['b']}",
"clra":f"moveq\t#0,{registers['a']}",
"clrb":f"moveq\t#0,{registers['b']}",
"deca":f"subq.b\t#1,{registers['a']}",
"decb":f"subq.b\t#1,{registers['b']}",
"inca":f"addq.b\t#1,{registers['a']}",
"incb":f"addq.b\t#1,{registers['b']}",
"lsra":f"lsr.b\t#1,{registers['a']}",   # for code that doesn't use "A" parameter for shift ops
"lsrb":f"lsr.b\t#1,{registers['b']}",   # for code that doesn't use "A" parameter for shift ops
"lsla":f"lsl.b\t#1,{registers['a']}",   # for code that doesn't use "A" parameter for shift ops
"lslb":f"lsl.b\t#1,{registers['b']}",   # for code that doesn't use "A" parameter for shift ops
"asla":f"asl.b\t#1,{registers['a']}",
"aslb":f"asl.b\t#1,{registers['b']}",
"asra":f"asr.b\t#1,{registers['a']}",
"asrb":f"asr.b\t#1,{registers['b']}",
"tsta":f"tst.b\t{registers['a']}",
"tstb":f"tst.b\t{registers['b']}",
"coma":f"not.b\t{registers['a']}",
"comb":f"not.b\t{registers['b']}",
"rora":f"roxr.b\t#1,{registers['a']}",
"rola":f"roxl.b\t#1,{registers['a']}",
"rorb":f"roxr.b\t#1,{registers['b']}",
"rolb":f"roxl.b\t#1,{registers['b']}",


"clv":f"CLR_V_FLAG",
}

AW = registers['awork1']
DW = registers['dwork1']

m68_regs = set(registers.values())


lab_prefix = "l_"

def add_entrypoint(address):
    addresses_to_reference.add(address)

def clear_reg(reg):
    return f"\tmoveq\t#0,{registers[reg]}{continuation_comment}\n"

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




def f_ldu(args,comment):
    return generic_load('u',args,comment,word=True)

# we load the 'stack'. Games then use this as auto variable memory
# but rarely hack on return address or saved registers so using the real 68000 stack
# pointer in that case is OK
def f_lds(args,comment):
    return generic_load('s',args,comment,word=True)

def f_lda(args,comment):
    return generic_load('a',args,comment)

def f_tst(args,comment):
    return generic_indexed_from("tst","",args,comment)

def f_ror(args,comment):
    return generic_shift_op("roxr","",args,comment)

def f_rol(args,comment):
    return generic_shift_op("roxl","",args,comment)

def f_lsr(args,comment):
    return generic_shift_op("lsr","",args,comment)

def f_lsl(args,comment):
    return generic_shift_op("lsl","",args,comment)

def f_asr(args,comment):
    return generic_shift_op("asr","",args,comment)

def f_asl(args,comment):
    return generic_shift_op("asl","",args,comment)

##def f_lsr(args,comment):
##    return generic_indexed_to("lsr","",args,comment)

def decode_movem(args):
    return_afterwards = False
    cc_move = False

    toks = set(args)

    must_make_d = registers['a'] in toks
    if "d" in toks:
        toks.discard("d")
        toks.add(registers['a'])
        toks.add(registers['b'])
    if "pc" in toks:
        toks.discard("pc")
        return_afterwards = True
    if "cc" in toks:
        toks.discard("cc")
        cc_move = True
    return "/".join(sorted(toks)),"movem" if len(toks)>1 else "move",return_afterwards,must_make_d,cc_move



# move.w would work except that... sign extension happens even on
# data registers, which then causes trouble when using long adds.
# it would be okay if all addresses were below 7FFF but most 6809 code
# uses addresses above 7FFF
def f_pshs(args,comment):
    move_params,inst,_,_,cc_move= decode_movem(args)
    if cc_move:
        rval = f"\tPUSH_SR{comment}"
    if move_params:
        rval += f"\n\t{inst}.l\t{move_params},-(sp){comment}"
    else:
        rval += "\n"
    return rval

def f_puls(args,comment):
    move_params,inst,return_afterwards,must_make_d,cc_move = decode_movem(args)
    if move_params:
        rval = f"\tmovem.l\t(sp)+,{move_params}{comment}"  # always movem to preserve flags by default
    else:
        rval = ""
    if must_make_d:
        # A was just restored: we have to rebuild D
        if cc_move:
            # cc is restored afterwards, no need to push/pop
            rval += f"\n{MAKE_D_PREFIX}".rstrip()
        else:
            rval += f"\n\tPUSH_SR{continuation_comment}\n{MAKE_D_PREFIX}\tPOP_SR{continuation_comment}"
    if cc_move:
        rval += f"\n\tPOP_SR{comment}"

    if return_afterwards:
        # pulling PC triggers a RTS (seen in Joust)
        rval += f"\n\trts{continuation_comment}"


    return rval

def f_ldd(args,comment):
    src = args[0]
    if src.startswith("#"):
        # immediate
        tok = src[1:]
        v = parse_hex(tok,tok)
        if v == tok:
            msb = f"(({v})>>8)"
        else:
            msb = f"{out_hex_sign}{v>>8:02x}"

        out = f"\tmove.b\t#{msb},{registers['a']}{comment}\n"
        if isinstance(v,int):
            source = f"{out_hex_sign}{v:04x}"
        else:
            source = v
        out += f"\tmove.w\t#{source},{registers['b']}{comment}"
    else:
        empty_inst = ""

        out = generic_indexed_from(empty_inst,"a",args,comment)
        out += f"\n\tLOAD_D{comment}"
    return out

def f_com(args,comment):
    return generic_indexed_to("not","",args,comment)
def f_neg(args,comment):
    return generic_indexed_to("neg","",args,comment)

def f_ldb(args,comment):
    return generic_load('b',args,comment)
def f_sta(args,comment):
    return generic_store('a',args,comment)
def f_stu(args,comment):
    return generic_store('u',args,comment,word=True)
def f_std(args,comment):
    return MAKE_D_PREFIX+generic_store('b',args,comment,word=True)
def f_stb(args,comment):
    return generic_store('b',args,comment)
def f_stx(args,comment):
    return generic_store('x',args,comment,word=True)
def f_sty(args,comment):
    return generic_store('y',args,comment,word=True)
def f_ldx(args,comment):
    return generic_load('x',args,comment, word=True)
def f_leax(args,comment):
    return generic_lea('x',args,comment)
def f_leay(args,comment):
    return generic_lea('y',args,comment)
def f_leau(args,comment):
    return generic_lea('u',args,comment)
def f_leas(args,comment):
    return generic_lea('s',args,comment)

def f_ldy(args,comment):
    return generic_load('y',args,comment, word=True)

def f_inc(args,comment):
    return generic_indexed_to("addq","#1",args,comment)
def f_dec(args,comment):
    return generic_indexed_to("subq","#1",args,comment)
def f_tfr(args,comment):
    srcreg = args[0]
    dstreg = args[1]
    double_size = {registers.get(x,x) for x in ["x","y","u","d"]}
    ext = "w" if srcreg in double_size or dstreg in double_size else "b"
    if dstreg == "dp":
        invreg = inv_registers[srcreg]
        # special case!
        if invreg == "A":
            out = f"\tSET_DP_FROM_A{comment}"
        else:
            out = f"\tSET_DP_FROM\t{srcreg}{comment}"
        return out

    out = "\tPUSH_SR\n"
    dest_d = False
    if srcreg=="d":
        out += MAKE_D_PREFIX
        srcreg=registers['b']
    if dstreg=="d":
        dest_d = True
        dstreg=registers['b']

    # condition flags not affected!
    out += f"\tmove.{ext}\t{srcreg},{dstreg}{comment}\n"
    if dest_d:
        rorreg = f"\tror.w\t#8,{srcreg}{continuation_comment}\n"
        out += f"{rorreg}\tmove.b\t{srcreg},{registers['a']}{continuation_comment} set MSB\n{rorreg}"

    out += "\tPOP_SR"
    return out

def f_clr(args,comment):
    return generic_store('#0',args,comment)



def generic_lea(dest,args,comment):

    quick = ""
    # add or sub
    first_arg = args[0]
    rval,first_arg = get_substitution_extended_reg(first_arg)     # from now on use work register, only first 8 bits are active

    inst = "add"
    if first_arg.startswith("-"):
        first_arg = first_arg[1:]
        inst = "sub"
    elif first_arg=="d":
        first_arg=registers['b']
        rval = MAKE_D_PREFIX
    elif first_arg and first_arg[0] in BRACKETS:
        # get address in memory
        args = [x.strip(BRACKETS) for x in args]
        # if 8 bit register, mask first
        rval = ""
        for arg in args:
            mask = "ff" if inv_registers.get(arg,arg) in "AB" else "ffff"
            if mask == "ff":
                rval += f"\tand.l\t#{out_hex_sign}{mask},{arg}{out_comment} mask register before add\n"

        if args[0] == 'd':
            args[0] = 'd0'

        rval += f"\tGET_INDIRECT_ADDRESS_REGS\t{args[0]},{args[1]},{registers[dest]}{comment}"
        return rval

    if first_arg and not is_register_value(first_arg):
        quick = "q" if can_be_quick(first_arg) else ""
        first_arg = f'#{first_arg}'

    if args[1]==registers[dest]:
        if first_arg:
            rval += f"\t{inst}{quick}.w\t{first_arg},{args[1]}{comment}"
    else:
        dest_68k = registers[dest]
        rval += f"\tmove.w\t{args[1]},{dest_68k}{comment}\n"
        if first_arg:
            rval += f"\t{inst}{quick}.w\t{first_arg},{dest_68k}{comment}"

    return rval

def unsupported_instruction(inst,args,comment):
    unknown_instructions.add(inst)
    return issue_warning(f"unknown/unsupported instruction {inst} with args {args}")+comment

def generic_load(dest,args,comment,word=False):
    return generic_indexed_from("move",dest,args,comment,word)
def generic_store(src,args,comment,word=False):
    return generic_indexed_to("move",src,args,comment,word)

def generic_shift_op(inst,reg,args,comment):
    arg = args[0]
    inst += ".b"
    if len(args)==2:

        offset = arg or "0"
        reg = args[1]

        rval = f"\tGET_REG_ADDRESS\t{offset},{reg}{comment}\n"
        rval += f"\t{inst}\t#1,({registers['awork1']}){comment}"
        return rval

    # sole argument: maybe can be register
    if arg in inv_registers:
        return f"\t{inst}\t#1,{arg}{comment}"
    else:
        gaf,arg,value = get_get_address_function(arg)

        # we have to load the address first
        rval = f"\t{gaf}\t{arg}{comment}\n"
        rval += f"\t{inst}\t#1,({registers['awork1']}){comment}"
        return rval

def generic_logical_op(inst,reg,args,comment):
    return generic_indexed_from(inst,reg,args,comment,word=False)

def f_lsra(args,comment):
    return generic_shift_op("lsr","a",args,comment)
def f_lsrb(args,comment):
    return generic_shift_op("lsr","b",args,comment)
def f_asla(args,comment):
    return generic_shift_op("asl","a",args,comment)
def f_aslb(args,comment):
    return generic_shift_op("asl","b",args,comment)
def f_rora(args,comment):
    return generic_shift_op("roxr","a",args,comment)
def f_rolb(args,comment):
    return generic_shift_op("roxl","b",args,comment)
def f_rorb(args,comment):
    return generic_shift_op("roxr","b",args,comment)
def f_rola(args,comment):
    return generic_shift_op("roxl","a",args,comment)
def f_ora(args,comment):
    return generic_logical_op("or","a",args,comment)
def f_bita(args,comment):
    return generic_logical_op("BIT","a",args,comment)
def f_bitb(args,comment):
    return generic_logical_op("BIT","b",args,comment)
def f_orb(args,comment):
    return generic_logical_op("or","b",args,comment)
def f_anda(args,comment):
    return generic_logical_op("and","a",args,comment)
def f_andcc(args,comment):
    # we can handle a few special cases
    arg = args[0]
    rval = None
    if arg.startswith("#"):
        v = int(arg[1:],16)
        if v==0xFE:
            # immediate value to mask out carry
            rval = f"\tCLR_XC_FLAGS{comment}"
        elif v==0xEF:
            rval = f"\tCLR_I_FLAG{comment}"


    return rval or unsupported_instruction("andcc",args,comment)

def f_orcc(args,comment):
    # we can handle a few special cases
    arg = args[0]
    rval = None
    if arg.startswith("#"):
        v = int(arg[1:],16)
        if v==0x1:
            # immediate value to mask out carry
            rval = f"\tSET_XC_FLAGS{comment}"
        elif v==0x10:
            rval = f"\tSET_I_FLAG{comment}"

    return rval or unsupported_instruction("orcc",args,comment)

def f_andb(args,comment):
    return generic_logical_op("and","b",args,comment)
def f_eora(args,comment):
    return generic_logical_op("eor","a",args,comment)
def f_eorb(args,comment):
    return generic_logical_op("eor","b",args,comment)

def f_adca(args,comment):
    return generic_indexed_from("addx",'a',args,comment)
def f_adcb(args,comment):
    return generic_indexed_from("addx",'b',args,comment)
def f_adda(args,comment):
    return generic_indexed_from("add",'a',args,comment)
def f_addb(args,comment):
    return generic_indexed_from("add",'b',args,comment)

def f_op_on_d(args,comment,op):
    rval = MAKE_D_PREFIX+generic_indexed_from(op,'b',args,comment,word=True)
    rval += f"\n\tPUSH_SR{continuation_comment}\n\tMAKE_A{continuation_comment}\n\tPOP_SR{continuation_comment}"
    return rval

def f_addd(args,comment):
    return f_op_on_d(args,comment,"add")

def f_subd(args,comment):
    return f_op_on_d(args,comment,"sub")

def f_suba(args,comment):
    return generic_indexed_from("sub",'a',args,comment)
def f_subb(args,comment):
    return generic_indexed_from("sub",'b',args,comment)
def f_sbca(args,comment):
    return generic_indexed_from("subx",'a',args,comment)

def f_sbcb(args,comment):
    return generic_indexed_from("subx",'b',args,comment)

def get_substitution_extended_reg(arg):
    if arg == registers['b'] or arg == registers['a']:
    # problem: using .w on B register actually picks D
    # also there's a sign extension to consider!
        DW = registers['dwork1']
        rval = f"""\tmoveq\t#0,{DW}{continuation_comment}
\tmove.b\t{arg},{DW}{continuation_comment} as byte
\tDO_EXTB\t{DW}{continuation_comment} with sign extension
"""
        return rval,DW
    else:
        return "",arg



def generic_indexed_to(inst,src,args,comment,word=False):
    arg = args[0]
    size = 2 if word else 1
    suffix = ".w" if word else ".b"
    if inst.islower():
        inst += suffix


    regsrc = registers.get(src,src)
    if regsrc:
        regsrc+=","

    if len(args)>1:
        # register indexed. There are many modes!
        index_reg = args[1]
        empty_first_arg = not args[0]
        if empty_first_arg:
            # 6809 mode that is not on 6502: ,X or ,X+...
            increment = args[1].count("+")
            decrement = args[1].count("-")
            sa = index_reg.strip("+-")
            rval = ""
            if decrement:
                rval = f"\tsubq.w\t#{decrement},{sa}{continuation_comment}\n"
            rval += f"\tGET_REG_ADDRESS\t0,{sa}{comment}\n"
            if increment:
                rval += f"\taddq.w\t#{increment},{sa}{continuation_comment}\n"


            rval += f"\t{inst}\t{regsrc}({registers['awork1']}){continuation_comment}"
            return rval

        else:
            sa = index_reg

            prefix = ""
            fromreg = ""
            if arg in inv_registers:
                # first argument is a register: convert back to Z80 register
                arg = inv_registers[arg].lower()

            z80_reg = arg

            rval = ""
            if arg in registers or arg=='d':
                fromreg = "_FROM_REG"

                if arg=='d':
                    prefix = "\tMAKE_D\n"
                    arg = registers['b']
                else:
                    arg = registers[arg]

                and_value = "FF" if z80_reg in ["a","b"] else "FFFF"
                rval  = f"\tand.l\t#{out_hex_sign}{and_value},{arg}{mask_out_comment}\n"

            rval += f"\tGET_REG_ADDRESS{fromreg}\t{arg},{sa}{comment}\n"


            rval += f"\t{inst}\t{regsrc}({registers['awork1']}){continuation_comment}"
            return rval



    else:
        if arg.startswith(OPENING_BRACKET):
            # indirect
            arg = arg.strip(BRACKETS)
            return f"""\tGET_INDIRECT_ADDRESS\t{arg}{comment}
\t{inst}\t{regsrc}({registers['awork1']}){continuation_comment}"""

    gaf,arg,value = get_get_address_function(arg)


    return f"""\t{gaf}\t{arg}{comment}
\t{inst}\t{regsrc}({registers['awork1']}){continuation_comment}"""

def generic_indexed_from(inst,dest,args,comment,word=False):
    """
    if inst is empty, just issue the address load
    """

    arg = args[0]
    rval,arg = get_substitution_extended_reg(arg) # from now on use work register, only first 8 bits are active

    size = "w" if word else "b"
    if inst and inst.islower():
        inst += f".{size}"


    y_indexed = False

    if arg.startswith(OPENING_BRACKET):
        # only 1 argument actually, re-merge args
        args = [",".join(args)]
        arg = args[0]

    regdst = registers[dest]
    if len(args)>1:
        # register indexed. There are many modes!
        index_reg = args[1]

        if arg=="":
            # direct without offset with possible increment: (6809 tested: ldd    ,x++)
            decrement = args[1].count("-")
            increment = args[1].count("+")
            sa = args[1].strip("+-")

            if decrement:
                rval += f"\tsubq.w\t#{decrement},{sa}{continuation_comment}\n"

            rval += f"\tGET_REG_ADDRESS\t0,{sa}{comment}\n"
            if increment:
                rval += f"\taddq.w\t#{increment},{sa}{continuation_comment}"
            if inst:
                rval += compose_instruction(inst,regdst)
            else:
                rval += "\n"

        else:
            # X/Y indexed direct (6809 tested: ldd    $0200,x or ldx d,x)
            invsa = inv_registers.get(index_reg)
            fromreg = ""
            prefix = ""

            if arg in inv_registers:
                # first argument is a register: convert back to Z80 register
                arg = inv_registers[arg].lower()

            z80_reg = arg



            if arg in registers or arg=='d':
                fromreg = "_FROM_REG"
                if arg=='d':
                    rval += "\tMAKE_D\n"
                    arg = registers['b']
                else:
                    arg = registers[arg]
                #and_value = "FF" if z80_reg in ["a","b"] else "FFFF"
                #prefix += f"\tand.l\t#{out_hex_sign}{and_value},{arg}{mask_out_comment}\n"


            rval += f"\tGET_REG_ADDRESS{fromreg}\t{arg},{index_reg}{comment}"
            if inst:
                rval  = rval.rstrip()+compose_instruction(inst,regdst)

        return rval
       # various optims
    else:
        if arg.startswith(OPENING_BRACKET):
            arg = arg.strip(BRACKETS)
            if "," in arg:
                # indexed
                arg,regsrc = arg.split(",")
                z80_reg = inv_registers[regsrc]
                if arg in inv_registers:
                    # first arg is also a register
                    out,arg = get_substitution_extended_reg(arg)
                    # if a or b, mask must be applied, sign extension and switch to work reg!
                    out += f"""\tGET_REG_REG_INDIRECT_ADDRESS\t{arg},{regsrc}{comment}
\t{inst}\t({registers['awork1']}),{regdst}{continuation_comment}"""
                else:
                    # first arg is a constant
                    out = f"""\tGET_REG_INDIRECT_ADDRESS\t{arg},{regsrc}{comment}
\t{inst}\t({registers['awork1']}),{regdst}{continuation_comment}"""
            else:
                out = f"""\tGET_INDIRECT_ADDRESS\t{arg}{comment}
\t{inst}\t({registers['awork1']}),{regdst}{continuation_comment}"""
            return out
        elif arg[0]=='#':
            # various optims for immediate mode
            if inst=="move.w":
                val = parse_hex(arg[1:],"WTF")
                if val == 0:
                    # move 0 => clr
                    return f"\tclr.{size}\t{regdst}{comment}"
            elif inst=="eor.b" and parse_hex(arg[1:])==0xff:
                # eor ff => not
                return f"\tnot.{size}\t{regdst}{comment}"

            return f"\t{inst}\t{arg},{regdst}{comment}"

    # we have to choose between GET_ADDRESS and GET_DP_ADDRESS
    # depending on the value of the argument
    gaf,arg,value = get_get_address_function(arg)

    out = f"\t{gaf}\t{arg}{comment}"
    if inst:
        out += compose_instruction(inst,regdst)

    return out

def get_get_address_function(arg):
    darg = arg.strip(">")
    try:
        value = parse_hex(darg)
    except ValueError:
        # identifier has been renamed: split and get the value
        value = int(darg.rsplit("_",1)[-1],16)


    if arg[0] == ">":
        # not direct mode, forced
        return "GET_ADDRESS",darg,value
    return ("GET_ADDRESS" if value >= 0x100 else "GET_DP_ADDRESS"),darg,value


def f_jmp(args,comment):
    target_address = None
    if not args[0] or args[0][0] in BRACKETS:
        return(f'\tERROR\t"indirect jmp"\t{comment}')
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


def generic_cmp(args,reg,comment,word=False):


    p = args[0]
    if p and p[0]=='#':
        size = "bw"[word]
        if parse_hex(p[1:],"WTF")==0:
            # optim
            out = f"\ttst.{size}\t{registers[reg]}{comment}"
        else:
            out = f"\tcmp.{size}\t{p},{registers[reg]}{comment}"
    else:
        out = generic_indexed_from("cmp",reg,args,comment,word)
    return out


def f_cmpu(args,comment):
    return generic_cmp(args,'u',comment,word=True)

def f_cmpd(args,comment):
    return "\tMAKE_D\n"+generic_cmp(args,'b',comment,word=True)

def f_cmpa(args,comment):
    return generic_cmp(args,'a',comment)

def f_cmpb(args,comment):
    return generic_cmp(args,'b',comment)

def f_cmpx(args,comment):
    return generic_cmp(args,'x',comment,word=True)

def f_cmpy(args,comment):
    return generic_cmp(args,'y',comment,word=True)

def f_exg(args,comment):
    return f"\texg\t{args[0]},{args[1]}{comment}"
def f_bsr(args,comment):
    return f_jsr(args,comment)

def f_jsr(args,comment):
    func = args[0]
    out = ""
    target_address = None
    if args[0][0] in BRACKETS:
        return(f'\tERROR\t"indirect jsr"\t{comment}')

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
def f_bhi(args,comment):
    return f_bcond("hi",args,comment)
def f_blo(args,comment):
    return f_bcond("lo",args,comment)
def f_ble(args,comment):
    return f_bcond("le",args,comment)
def f_bge(args,comment):
    return f_bcond("ge",args,comment)
def f_blt(args,comment):
    return f_bcond("lt",args,comment)
def f_bgt(args,comment):
    return f_bcond("gt",args,comment)
def f_bra(args,comment):
    return f_bcond("ra",args,comment)
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
def f_bls(args,comment):
    return f_bcond("ls",args,comment)

def f_bcond(cond,args,comment):
    func = args[0]
    out = ""
    target_address = None

    funcc = arg2label(func)
    if funcc != func:
        target_address = func
    func = funcc

    out += f"\t{branch_prefix}{cond}\t{func}{comment}"

    if target_address is not None:
        add_entrypoint(parse_hex(target_address))
    return out


def is_immediate_value(p):
    srcval = parse_hex(p,"FAIL")
    return srcval != "FAIL"

def is_register_value(p):
    return re.match("[ad]\d",p)

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
        inst = toks[0].strip().lower()

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
                out = unsupported_instruction(inst,"",comment)
        else:
            inst = itoks[0]
            args = itoks[1:]
            sole_arg = args[0].replace(" ","")
            # pre-process instruction to remove spaces
            # (only required when source is manually reworked, not in MAME dumps)
            #sole_arg = re.sub("(\(.*?\))",lambda m:m.group(1).replace(" ",""),sole_arg)

            # also manual rework for 0x03(ix) => (ix+0x03)
            sole_arg = re.sub("(-?0x[A-F0-9]+)\((\w+)\)",r"(\2+\1)",sole_arg)

            if inst.startswith("lb"):
                inst = inst[1:]   # merge long and short branches
            # other instructions, not single, not implicit a
            conv_func = globals().get(f"f_{inst}")

            def switch_reg(m):
                g1,g2 = m.groups()
                return g1 if g1 else registers.get(g2,g2)

            if conv_func:
                jargs = sole_arg.split(",")
                # switch registers now, warning, avoid changing $a by 0xd0!!
                hex_esc = re.escape(in_hex_sign)
                jargs = [re.sub(rf"({hex_esc}\w+)|(\b\w+)\b",switch_reg,a) for a in jargs]
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
                    out = f"\n"+unsupported_instruction(inst,args,comment)
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
        if in_hex_sign=="$" and out_hex_sign=="0x":
            # convert all $ labels to 0x in equates
            m = re.match("(\w+)\s*(=|equ)\s*\$(\w+)",l,flags=re.IGNORECASE)
            if m:
                out = "{} = 0x{}".format(m.group(1),m.group(3))
        elif out_hex_sign=="$" and in_hex_sign=="0x":
            # convert all 0x labels to $
            m = re.match("(\w+)\s*(=|equ)\s*0x(\w+)",l,flags=re.IGNORECASE)
            if m:
                out = "{} = ${}".format(m.group(1),m.group(3))

    if out and old_out != out:
        converted += 1
    else:
        out = l
    if not out.strip():
        # helps preserving original blank lines and differentiate them from generated
        # multiple blank lines that are more difficult not to generate :)
        out = "<blank>"

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

def remove_instruction(line):
    comment_pos = line.index(out_comment)
    return " "*comment_pos + line[comment_pos:]

def follows_sr_protected_block(nout_lines,i):
    # we have a chance of protected block only if POP_SR
    # was just before the branch test
    if i>0 and "POP_SR" not in nout_lines[i-1]:
        return False

##    for j in range(i-2,1,-1):
##        line = nout_lines[j]
##        if line.startswith("\trts"):
##            # sequence break:
##                return False
##
##        if line.startswith("\tPUSH_SR"):
##            # encountered POP then PUSH while going back
##            finst = nout_lines[j-1].split()[0]
##            return finst in carry_generating_instructions

    return True

# add review flag message in case of move.x followed by a branch
# also add review for writes to unlabelled memory
# also post-optimize stuff
prev_fp = None

reg_a = registers["a"]
clrxcflags_inst = ["CLR_XC_FLAGS"]
setxcflags_inst = ["SET_XC_FLAGS"]

# sub/add aren't included as they're the translation of dec/inc which don't affect C
# those are 68000 instructions (used in post-processing)
carry_generating_instructions = {"add","sub","cmp","lsr","lsl","asl","asr","roxr","roxl","subx","addx","abcd","CLR_XC_FLAGS","SET_XC_FLAGS"}
conditional_branch_instructions = {"bpl","bmi","bls","bne","beq","bhi","blo","bcc","bcs","blt","ble","bge","bgt"}
conditional_branch_instructions.update({f"j{x[1:]}" for x in conditional_branch_instructions})

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
                nout_lines[i] += issue_warning("stray bvc test",newline=True)
        elif finst == "bvs":
            if prev_fp:
                if prev_fp[0] == "tst.b":
                    change_tst_to_btst(nout_lines,i)
            else:
                nout_lines[i] += issue_warning("stray bvs test",newline=True)

        elif finst == "DAA" and prev_fp:
            # try to match add/sub + DAA and replace by abcd

            prev_inst = prev_fp[0]
            if prev_inst in ["addx.b","subx.b","add.b","sub.b"]:
                nout_lines[i] = ""
                tmpreg = registers['dwork1']
                clear_xc = "\tCLR_XC_FLAGS\n" if "addx" not in prev_inst and "subx" not in prev_inst else ""
                new_inst = prev_inst.replace("addx.b","abcd")
                new_inst = new_inst.replace("add.b","abcd")
                new_inst = new_inst.replace("subx.b","sbcd")
                new_inst = new_inst.replace("sub.b","sbcd")
                toks = prev_fp[1].split(",")
                if prev_inst in nout_lines[i-1]:
                    nout_lines[i-1] = f"""{clear_xc}\tmove.b\t{toks[0]},{tmpreg}\t{continuation_comment}
\t{new_inst}\t{tmpreg},{toks[1]}\t{continuation_comment}"""
                else:
                    # maybe a label or a comment was inserted there, can't process automatically
                    nout_lines[i] = issue_warning("stray daa, handle manually")

        elif finst == "MAKE_D" and prev_fp and prev_fp[0] == "LOAD_D":
            # no need to MAKE_D after LOAD_D
            nout_lines[i] = ""
        elif finst == "rts":
            # if previous instruction sets X flag properly, don't bother, but rol/ror do not!!
            if prev_fp:
                if prev_fp == ["movem.l","d0,-(sp)"]:
                    nout_lines[i] += issue_warning("push to stack+return",newline=True)
                elif prev_fp[0] == "cmp.b":
                    nout_lines[i] += issue_warning("stray cmp (check caller)",newline=True)

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
        elif finst not in conditional_branch_instructions and prev_fp and prev_fp[0] == "cmp.b":
                nout_lines[i] = issue_warning("review stray cmp (insert SET_X_FROM_CLEARED_C)",newline=True)+nout_lines[i]


        prev_fp = fp


# post-processing
grouping = True
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
            comment = "\t"+out_comment+line.split(out_comment)[1]
            first_param,second_param = split_params(toks[1])
            nout_lines_2.append(f"\tmove.b\t{first_param},{tmpreg}{comment}\n")
            nout_lines_2.append(line.replace(first_param,tmpreg)+"\n")
            continue
        if tok in {"roxr","roxl","ror","rol","lsr","asl","lsl","asr"} and "(" in toks[1]:
            # 68k can't handle such modes
            comment = "\t"+out_comment+line.split(out_comment)[1]
            first_param,second_param = split_params(toks[1])
            nout_lines_2.append(f"\tmove.b\t{second_param},{tmpreg}{comment}\n")
            nout_lines_2.append(line.replace(second_param,tmpreg)+"\n")
            nout_lines_2.append("\tPUSH_SR\n")
            nout_lines_2.append(f"\tmove.b\t{tmpreg},{second_param}{comment}\n")
            nout_lines_2.append("\tPOP_SR\n")
            continue
        elif tok in {"addx","subx"}:
            comment = "\t|"+line.split(out_comment)[1]
            first_param,second_param = split_params(toks[1])
            if "(" in first_param or '#' in first_param:
                # 68k can't handle such modes
                nout_lines_2.append(f"\tmove.b\t{first_param},{tmpreg}{comment}\n")
                nout_lines_2.append(line.replace(first_param,tmpreg)+"\n")
                continue
    if line:
        if line.startswith("<blank>"):
            line = ""
        nout_lines_2.append(line+"\n")

nout_lines = []
# ultimate passes to process POP+PUSH
# remove PUSH following POP
prev_line = ""
last_get_address = None
last_dir = None

for line in nout_lines_2:
    toks = line.split()
    if toks:
        if toks[0] in ("GET_ADDRESS","GET_DP_ADDRESS"):
            if last_get_address == toks[1] and last_dir == toks[0]:
                line = remove_instruction(line)
            last_dir = toks[0]
            last_get_address = toks[1]
        elif not toks[0].startswith(("move","add","sub","or","and")):
            # cancel duplicate same get_address call when we're not sure!
            last_get_address = None
        if toks[0] == "nop":
            line = remove_instruction(line)

    if "POP_SR" in prev_line and "PUSH_SR" in line:
        # remove both
        nout_lines.pop()
        continue
    if "LOAD_D" in prev_line and "MAKE_D" in line:
        # remove MAKE_D
        continue

    # if move.w in line and (ax) replace move.w by cpu-dependent macro
    if "move.w" in line and f"({AW})" in line:
        if ",(" in line:
            inst = "MOVE_W_FROM_REG"
        else:
            inst = "MOVE_W_TO_REG"
        line = line.replace("move.w",inst).replace(f"({AW})",AW).replace(f"({AW})".lower(),AW)

    # optimize move.b => clr.b
    line = line.replace("move.b\t#0,","clr.b\t")
    nout_lines.append(line)
    prev_line = line

# another pass after ror has been resolved
for i,line in enumerate(nout_lines):
    line = line.rstrip()
    toks = line.split("|",maxsplit=1)
    if len(toks)==2:
        fp = toks[0].rstrip().split()
        if fp:
            finst = fp[0]
            if finst in ("bcc","bcs","jcc","jcs"):
                # if previous instruction sets X flag properly, don't bother, but rol/ror do not!!
                if prev_fp:
                    inst_no_size = prev_fp[0].split(".")[0]
                    if inst_no_size not in carry_generating_instructions and inst_no_size not in conditional_branch_instructions:
                        if not follows_sr_protected_block(nout_lines,i):
                            nout_lines[i] += issue_warning("stray bcc/bcs test",newline=True)
        prev_fp = fp
        if re.search("GET_.*_ADDRESS",toks[0]) and follows_sr_protected_block(nout_lines,i):
            if "PUSH_SR" in nout_lines[i-3]:
                # PUSH/op/POP+GET_xxx_ADDRESS
                # no need to protect CCs as there's a GET_xxx_ADDRESS (so not a test) just after it
                nout_lines[i-1] = ""
                nout_lines[i-3] = ""

if cli_args.spaces:
    nout_lines = [tab2space(n) for n in nout_lines]


f = io.StringIO()

if True:
    X = registers['x']
    Y = registers['y']
    U = registers['u']
    A = registers['a']
    B = registers['b']

    f.write(f"""{out_start_line_comment} Converted with 6809to68k by JOTD
{out_start_line_comment}
{out_start_line_comment} make sure you call "cpu_init" first so all bits of data registers
{out_start_line_comment} are zeroed out so we can use add.l dy,ax with dy > 0x7FFF
{out_start_line_comment} without systematic masking
{out_start_line_comment}
{out_start_line_comment} WARNING: you also have to call "cpu_init"
{out_start_line_comment} at start of any interrupt you could hook
{out_start_line_comment}
{out_start_line_comment} the GET_ADDRESS macro can just call get_address or it can also use
{out_start_line_comment} conditional compilation to select the proper memory banks at compile time
{out_start_line_comment} (see my burger time 6502 conversion which does that in RELEASE mode)


""")

    if cli_args.output_mode == "mit":
        f.write(f"""
\t.global\tcpu_init
\t.global\tm6809_direct_page_pointer

\t.macro\tERROR\targ
\t.error\t"\\arg"     | comment out to disable errors
\t.endm

\t.macro\tVIDEO_BYTE_DIRTY
\t{out_comment} called when a byte write was done in {AW}
\t.endm

\t.macro\tVIDEO_WORD_DIRTY
\t{out_comment} called when a word write was done in {AW}
\t.endm

\t.macro\tGET_ADDRESS_FUNC
\tjbsr\tget_address
\t.endm

\t.macro\tGET_UNCHECKED_ADDRESS_FUNC
\tjbsr\tget_address
\t.endm

\t.macro\tABX
\tmoveq\t#0,{DW}
\tmove.b\t{B},{DW}
\tadd.w\t{B},{X}
\t.endm


\t.macro\tSEX
\tmove.b\t{B},{A}
\text.b\t{A}
\t.endm

\t.macro\tMAKE_D
{out_start_line_comment} add value of A in B MSB so D&0xFF == B
\trol.w\t#8,{B}
\tmove.b\t{A},{B}
\trol.w\t#8,{B}
\t.endm

\t.macro\tMAKE_A
\trol.w\t#8,{B}
\tmove.b\t{B},{A}
\trol.w\t#8,{B}
\t.endm

\t.macro\tBIT\treg,arg
\tmove.b\t\\reg,{DW}
\tand.b\t\\arg,{DW}
\t.endm


\t.macro\tLOAD_D
\tmove.b\t({AW}),d0
\tmove.b\t(1,{AW}),d1
\tMAKE_D
\t.endm

\t.macro CLR_XC_FLAGS
\tmove.w\td7,-(a7)
\tmoveq\t#0,{DW}
\troxl.b\t#1,{DW}
\tmovem.w\t(a7)+,{DW}
\t.endm

\t.macro SET_XC_FLAGS
\tmove.w\t{DW},-(a7)
\tst\t{DW}
\troxl.b\t#1,{DW}
\tmovem.w\t(a7)+,{DW}
\t.endm



\t.macro INVERT_XC_FLAGS
\tPUSH_SR
\tmove.w\t(sp),{DW}
\teor.b\t#0x11,{DW}
\tmove.w\t{DW},(sp)
\tPOP_SR
\t.endm

{out_start_line_comment} useful to recall C from X (add then move then bcx)
\t.macro\tSET_C_FROM_X
\tPUSH_SR
\tmove.w\t(sp),{DW}
\tbset\t#0,{DW}   | set C
\tbtst\t#4,{DW}
\tjne\t0f
\tbclr\t#0,{DW}   | X is clear: clear C
0:
\tmove.w\t{DW},(sp)
\tPOP_SR
\t.endm

\t.macro\tSET_X_FROM_CLEARED_C
\tPUSH_SR
\tmove.w\t(sp),{DW}
\tbset\t#4,{DW}   | set X
\tbtst\t#0,{DW}
\tjeq\t0f
\tbclr\t#4,{DW}   | C is set: clear X
0:
\tmove.w\t{DW},(sp)
\tPOP_SR
\t.endm


\t.macro SET_I_FLAG
\t{error}\t"TODO: insert interrupt disable code here"
\t.endm
\t.macro CLR_I_FLAG
\t{error}\t"TODO: insert interrupt enable code here"
\t.endm

\t.macro\tJXX_A_INDEXED
\tand.w\t#0xFF,{A}  {out_comment} mask 8 bits
\tadd.w\t{A},{A}    {out_comment} *2 (16 -> 32 bits)
\t.endm

\t.ifdef\tMC68020


* 68020 compliant & optimized

\t.macro DO_EXTB\treg
\textb.l\t\\reg
\t.endm

\t.macro PUSH_SR
\tmove.w\tccr,-(sp)
\t.endm
\t.macro POP_SR
\tmove.w\t(sp)+,ccr
\t.endm


\t.macro\tMOVE_W_TO_REG\tsrc,dest
\tmove.w\t(\\src),\\dest
\t.endm

\t.macro\tMOVE_W_FROM_REG    src,dest
\tmove.w\t\\src,(\\dest)
\t.endm

\t.macro\tJSR_A_INDEXED\treg
\tJXX_A_INDEXED
\tjsr\t([\\reg,{A}.W])
\t.endm
\t.macro\tJMP_A_INDEXED\treg
\tJXX_A_INDEXED
\tjmp\t([\\reg,{A}.W])
\t.endm

\t.macro READ_BE_WORD\tsrcreg
\tmoveq\t#0,{DW}
\tmove.w\t(\\srcreg),{DW}
\tmove.l\t{DW},\\srcreg
\t.endm

\t.else

* 68000 compliant

\t.macro DO_EXTB\treg
\text\t\\reg
\text.l\t\\reg
\t.endm

\t.macro PUSH_SR
\tmove.w\tsr,-(sp)
\t.endm
\t.macro POP_SR
\tmove.w\t(sp)+,sr
\t.endm

\t.macro\tMOVE_W_TO_REG    src,dest
\tror.w\t#8,\\dest
\tmove.b\t(\\src),\\dest
\tror.w\t#8,\\dest
\tmove.b\t(1,\\src),\\dest
\t.endm

\t.macro\tMOVE_W_FROM_REG    src,dest
\tror.w\t#8,\\src
\tmove.b\t\\src,(\\dest)
\tror.w\t#8,\\src
\tmove.b\t\\src,(1,\\dest)
\t.endm




\t.macro\tJSR_A_INDEXED\treg
\tJXX_A_INDEXED
\tmove.l\t(\\reg,{A}.w),\\reg
\tjsr\t(\\reg)
\t.endm

\t.macro\tJMP_A_INDEXED\treg
\tJXX_A_INDEXED
\tmove.l\t(\\reg,{A}.w),\\reg
\tjmp\t(\\reg)
\t.endm

\t.macro READ_BE_WORD\tsrcreg
\tmoveq\t#0,{DW}
\tmove.b\t(\\srcreg),{DW}
\tlsl.w\t#8,{DW}
\tmove.b\t(1,\\srcreg),{DW}
\tmove.l\t{DW},\\srcreg
\t.endm

\t.endif




* registers must be masked out to proper size before use
\t.macro\tGET_INDIRECT_ADDRESS_REGS\treg1,reg2,destreg
\tmove.l\t\\reg1,{AW}
\tadd.l\t\\reg2,{AW}
\tGET_ADDRESS_FUNC
\tMOVE_W_TO_REG\t{AW},\\destreg
\t.endm


\t.macro GET_DP_ADDRESS\toffset
\tlea\t({registers['dp_base']},\\offset\\().W),{AW}
\t.endm


\t.macro SET_DP_FROM_A
\tlsl.w    #8,{registers['a']}
\tmove.l    {registers['a']},{AW}
\tGET_ADDRESS_FUNC
\tmove.l\t{AW},{registers['dp_base']}
\tmove.l\t{registers['dp_base']},m6809_direct_page_pointer
\tlsr.w    #8,{registers['a']}
\t.endm



\t.macro SET_DP_FROM    reg
\texg\t{registers['a']},\\reg
\tSET_DP_FROM_A

\texg\t{registers['a']},\\reg
\t.endm

""")
        for unchecked in ["","UNCHECKED_"]:
            f.write(f"""\t.macro GET_REG_{unchecked}ADDRESS\toffset,reg
\t.ifeq\t\\offset
\tmove.l\t\\reg,{AW}
\t.else
\tlea\t\\offset,{AW}
\tadd.l\t\\reg,{AW}
\t.endif
\tGET_{unchecked}ADDRESS_FUNC
\t.endm


\t.macro GET_REG_INDIRECT_{unchecked}ADDRESS\toffset,reg
\tGET_REG_ADDRESS\t\\offset,\\reg
\tREAD_BE_WORD\t{AW}
\tGET_{unchecked}ADDRESS_FUNC
\t.endm

\t.macro    GET_REG_REG_{unchecked}INDIRECT_ADDRESS reg1,reg2
\tGET_INDIRECT_ADDRESS_REGS\t\\reg1,\\reg2,{DW}
\tand.l\t#0xFFFF,{DW}
\tmove.l\t{DW},{AW}
\tGET_{unchecked}ADDRESS_FUNC
\t.endm

\t.macro GET_REG_{unchecked}ADDRESS_FROM_REG\treg,reg2
\tmove.l\t\\reg,{AW}
\tadd.l\t\\reg2,{AW}
\tGET_{unchecked}ADDRESS_FUNC
\t.endm

\t.macro GET_{unchecked}ADDRESS\toffset
\tlea\t\\offset,{AW}
\tGET_{unchecked}ADDRESS_FUNC
\t.endm

\t.macro GET_INDIRECT_{unchecked}ADDRESS\toffset
\tGET_ADDRESS\t\\offset
\tREAD_BE_WORD\t{AW}
\tGET_{unchecked}ADDRESS_FUNC
\t.endm
""")
    else:
        # MOT macros are not up to date for now
        f.write(f"""SBC_X:MACRO
\tINVERT_XC_FLAGS
\tGET_ADDRESS\t\\1
\tmove.b\t({registers['awork1']},{X}.w),{DW}
\tsubx.b\t{DW},{A}
\tINVERT_XC_FLAGS
\tENDM
\t
SBC_Y:MACRO
\tINVERT_XC_FLAGS
\tGET_ADDRESS\t\\1
\tmove.b\t({AW},{Y}.w),{DW}
\tsubx.b\t{DW},{A}
\tINVERT_XC_FLAGS
\tENDM
\t
SBC:MACRO
\tINVERT_XC_FLAGS
\tGET_ADDRESS\t\\1
\tmove.b\t({AW}),{DW}
\tsubx.b\t{DW},{A}
\tINVERT_XC_FLAGS
\tENDM

SBC_IMM:MACRO
\tINVERT_XC_FLAGS
\tmove.b\t#\\1,{DW}
\tsubx.b\t{DW},{A}
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
^^^^ TODO: insert interrupt disable code here
\tENDM

CLR_I_FLAG:MACRO
^^^^ TODO: insert interrupt enable code here
\tENDM

\tIFD\tMC68020
\tPUSH_SR:MACRO
\tmove.w\tccr,-(sp)
\tENDM
POP_SR:MACRO
\tmove.w\t(sp)+,ccr
\tENDM
\t.else
PUSH_SR:MACRO
\tmove.w\tsr,-(sp)
\tENDM
POP_SR:MACRO
\tmove.w\t(sp)+,sr
\tENDM
\tENDC

READ_LE_WORD:MACRO
\tmove.b\t(1,\\1),{DW}
\tlsl.w\t#8,{DW}
\tmove.b\t(\\1),{DW}
\tmove.w\t{DW},\\1
\tENDM

GET_ADDRESS:MACRO
\tlea\t\\1,{registers['awork1']}
\tGET_ADDRESS_FUNC
\tENDM


""")
    f.write("* zero all registers but 6809 stack pointer\n")
    f.write("cpu_init:\n")
    for i in range(8):
        reg = f"d{i}"
        if reg != registers["s"]:
            f.write(f"\tmoveq\t#0,{reg}\n")
    f.write("\trts\n\n")

    f.write(f"""get_address:
\t{error} "`TODO: implement this by adding memory base to {registers['awork1']}"
\trts

{out_comment} direct page pointer needs to be reloaded in case of irq
m6809_direct_page_pointer:
\t.long\t{out_hex_sign}A5A5A5A5

""")

if os.path.exists(cli_args.include_output):
    print(f"Skipping already created file {cli_args.include_output}")
else:
    print(f"Generating file {cli_args.include_output}")
    with open(cli_args.include_output,"w") as fw:
        fw.write(f.getvalue())
        A =registers['a']
        B =registers['b']
        fw.write(f"""
multiply_ab:
\tand.w\t#{out_hex_sign}FF,{A}
\tand.w\t#{out_hex_sign}FF,{B}
\tmulu\t{A},{B}
\tror.w\t#8,{B}
\tmove.b\t{B},{A}
\tror.w\t#8,{B}
\trts
""")

buffer = f"""\t.include "{cli_args.include_output}"

"""+"".join(nout_lines)

# remove review flags if requested (not recommended!!)
if cli_args.no_review:
    nout_lines = [line for line in buffer.splitlines(True) if "{error}" not in line]
else:
    nout_lines = [line for line in buffer.splitlines(True)]

with open(cli_args.code_output,"w") as f:
    f.writelines(nout_lines)


print(f"Converted {converted} lines on {len(lines)} total, {instructions} instruction lines")
print(f"Converted instruction ratio {converted}/{instructions} {int(100*converted/instructions)}%")
if unknown_instructions:
    print(f"Unknown/fully or partially unsupported instructions: ")
    for s in sorted(unknown_instructions):
        if "nop" in s:
            print("  unofficial nop")
        else:
            print(f"  {s}")
else:
    print("No unknown instructions")

print("\nPLEASE REVIEW THE CONVERTED CODE CAREFULLY AS IT MAY CONTAIN ERRORS!\n")
print("(some TODO: review lines may have been added, and the code won't build on purpose)")




