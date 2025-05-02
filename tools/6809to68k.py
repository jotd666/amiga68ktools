# TODO:
#
#  direct mode with page, debug a lot of instructions
# $f6fb: lda    >$0000 ????
#
# generic_shift_op: remainders of 6502: crash if not a register ATM
#  andcc
#  lds
#


# post_proc: tst.w + GET_.*ADDRESS => remove tst.w
# set macro MOVE_W for alignment (68000/68020) in post processing if source or dest
# is not a register, detect others .w operands in that case

# you'll have to implement the macro GET_ADDRESS_BASE to return pointer on memory layout
# to replace lea/move/... in memory
# extract RAM memory constants as defines, not variables
# work like an emulator
#
# this is completely different from Z80. Easier for registers, but harder
# for memory because of those indirect indexed modes that read pointers from memory
# so we can't really map 32-bit model on original code without heavily adapting everything
#

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
error = ".error"

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
    rval =  f'\t.error\t"review {msg}"'
    if newline:
        rval += "\n"
    return rval

# convention:
# a => d0
# x => d1
# y => d2
# u => d3

registers = {
"a":"d0","b":"d1","x":"d2","y":"d3","u":"d4","c":"d5",
"dwork1":"d6",
"dwork2":"d7",
"awork1":"a0",
#"p":"sr",
"base":"a6"}
inv_registers = {v:k.upper() for k,v in registers.items()}



single_instructions = {"nop":"nop",
"rts":"rts",
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
"rora":f"roxr\t#1,{registers['a']}",
"rola":f"roxl\t#1,{registers['a']}",
"rorb":f"roxr\t#1,{registers['b']}",
"rolb":f"roxl\t#1,{registers['b']}",


"php":"PUSH_SR",
"plp":"POP_SR",

"sec":"SET_XC_FLAGS",
"clc":"CLR_XC_FLAGS",
"sei":"SET_I_FLAG",
"cli":"CLR_I_FLAG",
"sed":"illegal\n"+issue_warning("unsupported set decimal mode"),
"cld":"nop",
"clv":f"CLR_V_FLAG",
}

m68_regs = set(registers.values())


lab_prefix = "l_"

def add_entrypoint(address):
    addresses_to_reference.add(address)

def clear_reg(reg):
    return f"\tmoveq\t#0,{registers[reg]}\n"

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

def f_lda(args,comment):
    return generic_load('a',args,comment)

def f_ldd(args,comment):
    src = args[0]
    if src.startswith("#"):
        # immediate
        tok = src[1:]
        v = parse_hex(tok,tok)
        if v == tok:
            msb = f"(({v})>>8)"
            lsb = f"(({v})&0xFF)"
        else:
            msb = f"{out_hex_sign}{v>>8:02x}"
            lsb = f"{out_hex_sign}{v&0xFF:02x}"

        out = f"\tmove.b\t#{msb},{registers['a']}{comment}\n"
        out += f"\tmove.b\t#{lsb},{registers['b']}{comment}"
    else:
        out = f_lda(args,comment)
        out += f"\n\tmove.b\t(1,{registers['awork1']}),{registers['b']}{comment}"
    out += f"\n\tMAKE_D{comment}\n\ttst.w\t{registers['a']}{comment}"
    return out

def f_ldb(args,comment):
    return generic_load('b',args,comment)
def f_sta(args,comment):
    return generic_store('a',args,comment)
def f_stu(args,comment):
    return generic_store('u',args,comment)
def f_std(args,comment):
    return "\tMAKE_D\n"+generic_store('a',args,comment,word=True)
def f_stb(args,comment):
    return generic_store('b',args,comment)
def f_stx(args,comment):
    return generic_store('x',args,comment)
def f_sty(args,comment):
    return generic_store('y',args,comment)
def f_ldx(args,comment):
    return clear_reg('x') + generic_load('x',args,comment, word=True)
def f_leax(args,comment):
    return generic_lea('x',args,comment)
def f_leay(args,comment):
    return generic_lea('y',args,comment)
def f_leau(args,comment):
    return generic_lea('u',args,comment)

def f_ldy(args,comment):
    return clear_reg('x') + generic_load('y',args,comment, word=True)

def f_inc(args,comment):
    return generic_indexed_to("addq","#1",args,comment)
def f_dec(args,comment):
    return generic_indexed_to("subq","#1",args,comment)
def f_tfr(args,comment):
    srcreg = args[0]
    dstreg = args[1]
    double_size = ["x","y","u","d"]
    ext = "w" if srcreg in double_size or dstreg in double_size else "b"
    if dstreg == "dp":
        invreg = inv_registers[srcreg]
        # special case!
        if invreg == "A":
            out = f"\tSET_DP_FROM_A{comment}"
        else:
            out = f"\tSET_DP_FROM\t{srcreg}{comment}"
        return out

    if srcreg=="d":
        srcreg=registers['a']
    if dstreg=="d":
        dstreg=registers['a']

    # condition flags not affected!
    out = f"\tPUSH_SR\n\tmove.{ext}\t{srcreg},{dstreg}{comment}\n\tPOP_SR"

    return out

def f_clr(args,comment):
    return generic_store('#0',args,comment)

def generic_lea(dest,args,comment):
    rval = ""
    quick = ""
    if args[1]==registers[dest]:
        # add or sub
        first_arg = args[0]
        inst = "add"
        if first_arg[0]=="-":
            first_arg = first_arg[1:]
            inst = "sub"
        elif first_arg=="d":
            first_arg=registers['a']
            rval = "\tMAKE_D\n"
        if is_immediate_value(first_arg):
            quick = "q" if parse_hex(first_arg) < 0x10 else ""
            first_arg = f'#{first_arg}'
        rval += f"\t{inst}{quick}.w\t{first_arg},{args[1]}{comment}"

    else:
        rval = f'\t{error} "unsupported lea {dest} {args}"'

    return rval

def generic_load(dest,args,comment,word=False):
    return generic_indexed_from("move",dest,args,comment,word)
def generic_store(src,args,comment,word=False):
    return generic_indexed_to("move",src,args,comment,word)

def generic_shift_op(inst,reg,args,comment):
    arg = args[0]
    inst += ".b"
    if arg==registers[reg]:
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
def f_orb(args,comment):
    return generic_logical_op("or","b",args,comment)
def f_anda(args,comment):
    return generic_logical_op("and","a",args,comment)
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
def f_addd(args,comment):
    return "\tMAKE_D\n"+generic_indexed_from("add",'a',args,comment,word=True)
def f_suba(args,comment):
    return generic_indexed_from("sub",'a',args,comment)
def f_subb(args,comment):
    return generic_indexed_from("sub",'b',args,comment)
def f_sbca(args,comment):
    return generic_indexed_from("subx",'a',args,comment)
def f_sbcb(args,comment):
    return generic_indexed_from("subx",'b',args,comment)

def generic_indexed_to(inst,src,args,comment,word=False):
    arg = args[0]
    size = 2 if word else 1
    suffix = ".w" if word else ".b"
    if inst.islower():
        inst += suffix
    y_indexed = False
    regsrc = registers.get(src,src)
    if len(args)>1:
        # register indexed. There are many modes!
        index_reg = args[1]
        empty_first_arg = not args[0]
        if empty_first_arg:
            # 6809 mode that is not on 6502: ,X or ,X+...
            increment = args[1].count("+")
            sa = index_reg.strip("+")
            invsa = inv_registers.get(sa)
            rval = f"\tGET_{invsa.upper()}_ADDRESS\t0{comment}\n"
            if increment:
                rval += f"\taddq.w\t#{increment},{sa}\n"

            rval += f"\t{inst}\t{regsrc},({registers['awork1']}){out_comment} [...]"
            return rval

        else:
            sa = index_reg
            invsa = inv_registers.get(sa)
            rval = f"\tGET_{invsa.upper()}_ADDRESS\t{arg}{comment}\n"

            rval += f"\t{inst}\t{regsrc},({registers['awork1']}){out_comment} [...]"
            return rval
    else:
        if arg.startswith(OPENING_BRACKET):
            # indirect
            arg = arg.strip(BRACKETS)
            return f"""\tGET_INDIRECT_ADDRESS\t{arg}{comment}
\t{inst}\t{regsrc},({registers['awork1']}){out_comment} [...]"""

    return f"""\tGET_ADDRESS\t{arg}{comment}
\t{inst}\t{regsrc},({registers['awork1']}){out_comment} [...]"""

def generic_indexed_from(inst,dest,args,comment,word=False):
    arg = args[0]

    size = "w" if word else "b"
    if inst.islower():
        inst += f".{size}"
    y_indexed = False

    regdst = registers[dest]
    if len(args)>1:
        # register indexed. There are many modes!
        index_reg = args[1]

        if arg=="":
            # direct without offset with possible increment: (6809 tested: ldd    ,x++)
            increment = args[1].count("+")
            sa = args[1].strip("+")
            invsa = inv_registers.get(sa)
            rval = f"\tGET_{invsa.upper()}_ADDRESS\t0{comment}\n"
            if increment:
                rval += f"\taddq.w\t#{increment},{sa}\n"

            rval += f"\t{inst}\t(a0),{regdst}{out_comment} [...]"
            return rval
        else:
            # X/Y indexed direct (6809 tested: ldd    $0200,x)
            invsa = inv_registers.get(index_reg)
            return f"""\tGET_{invsa.upper()}_ADDRESS\t{arg}{comment}
\t{inst}\t({registers['awork1']}),{regdst}{out_comment} [...]"""
       # various optims
    else:
        if arg.startswith(OPENING_BRACKET):
            # Y indirect indexed untested
            arg = arg.strip(BRACKETS)
            out = f"""\tGET_INDIRECT_ADDRESS\t{arg}{comment}
\t{inst}\t({registers['awork1']}),{regdst}{out_comment} [...]"""
            return out
        elif arg[0]=='#':
            # various optims for immediate mode
            if inst=="move.b":
                if word:
                    inst = "move.w"
                val = parse_hex(arg[1:],"WTF")
                if val == 0:
                    # move 0 => clr
                    return f"\tclr.{size}\t{regdst}{comment}"
            elif inst=="eor.b" and parse_hex(arg[1:])==0xff:
                # eor ff => not
                return f"\tnot.{size}\t{regdst}{comment}"

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


def generic_cmp(args,reg,comment,word=False):


    p = args[0]
    if p[0]=='#':
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

def f_cmpa(args,comment):
    return generic_cmp(args,'a',comment)

def f_cmpb(args,comment):
    return generic_cmp(args,'b',comment)

def f_cmpx(args,comment):
    return generic_cmp(args,'x',comment)

def f_cmpy(args,comment):
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
def f_bhi(args,comment):
    return f_bcond("hi",args,comment)
def f_blo(args,comment):
    return f_bcond("lo",args,comment)
def f_ble(args,comment):
    return f_bcond("le",args,comment)
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
                unknown_instructions.add(inst)
                out = f'\t{error}\tunknown instruction {inst}"{comment}'
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
                    out = f"{l}\n"+issue_warning(f"unknown/unsupported instruction {inst}")
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
carry_generating_instructions = {"add","sub","cmp","lsr","asl","roxr","roxl","subx","addx"}

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

        elif finst in ("bcc","bcs"):
            # if previous instruction sets X flag properly, don't bother, but rol/ror do not!!
            if prev_fp:
                inst_no_size = prev_fp[0].split(".")[0]
                if inst_no_size not in carry_generating_instructions:
                    if not follows_sr_protected_block(nout_lines,i):
                        nout_lines[i] += issue_warning("stray bcc/bcs test",newline=True)

        elif finst == "rts":
            # if previous instruction sets X flag properly, don't bother, but rol/ror do not!!
            if prev_fp:
                if prev_fp == ["movem.w","d0,-(sp)"]:
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
        elif finst not in ["bne","beq"] and prev_fp and prev_fp[0] == "cmp.b":
                nout_lines[i] = issue_warning("review stray cmp (insert SET_X_FROM_CLEARED_C)",newline=True)+nout_lines[i]

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
            comment = "\t"+out_comment+line.split(out_comment)[1]
            first_param,second_param = split_params(toks[1])
            nout_lines_2.append(f"\tmove.b\t{first_param},{tmpreg}{comment}\n")
            nout_lines_2.append(line.replace(first_param,tmpreg)+"\n")
            continue
        if tok in {"roxr","roxl","ror","rol","lsr","asl"} and "(" in toks[1]:
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
            comment = "\t|"+line.split(in_comment)[1]
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
    U = registers['u']
    A = registers['a']
    C = registers['c']
    V = "WTF"
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


\t.macro\tMAKE_D
\trol.w\t#8,{registers['a']}
\tmove.b\t{registers['b']},{registers['a']}
\trol.w\t#8,{registers['a']}
\t.endm


\t.macro\tMAKE_B
\tmove.w\t{registers['a']},{registers['b']}
\trol.w\t#8,{registers['b']}
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

\t.macro CLR_XC_FLAGS
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
    {error}   "TODO: insert interrupt disable code here"
\t.endm
\t.macro CLR_I_FLAG
    {error}   "TODO: insert interrupt enable code here"
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

\t.macro READ_BE_WORD\tsrcreg
\tmove.b\t(\\srcreg),{registers['dwork1']}
\tlsl.w\t#8,{registers['dwork1']}
\tmove.b\t(1,\\srcreg),{registers['dwork1']}
\tmove.w\t{registers['dwork1']},\\srcreg
\t.endm

\t.macro GET_ADDRESS\toffset
\tlea\t\offset,{registers['awork1']}
\tjbsr\tget_address
\t.endm


\t.macro GET_INDIRECT_ADDRESS\toffset
\tGET_ADDRESS\t\\offset
\tREAD_BE_WORD\t{registers['awork1']}
\tjbsr\tget_address
\t.endm

\t.macro SET_DP_FROM_A
\t{error}  "implement this!!"
\t.endm

\t.macro SET_DP_FROM    \\reg
\texg\t{registers['a']},\\reg
\tSET_DP_FROM_A

\texg\t{registers['a']},\\reg
\t.endm

""")
        for reg in "xyu":
            f.write(f"""\t.macro GET_{reg.upper()}_ADDRESS\toffset
\tlea\t\\offset,{registers['awork1']}
\tadd.l\t{registers[reg]},{registers['awork1']}
\tjbsr\tget_address
\t.endm

""")
    else:
        # MOT macros are not up to date for now
        f.write(f"""SBC_X:MACRO
\tINVERT_XC_FLAGS
\tGET_ADDRESS\t\\1
\tmove.b\t({registers['awork1']},{X}.w),{W}
\tsubx.b\t{W},{A}
\tINVERT_XC_FLAGS
\tENDM
\t
SBC_Y:MACRO
\tINVERT_XC_FLAGS
\tGET_ADDRESS\t\\1
\tmove.b\t({registers['awork1']},{Y}.w),{W}
\tsubx.b\t{W},{A}
\tINVERT_XC_FLAGS
\tENDM
\t
SBC:MACRO
\tINVERT_XC_FLAGS
\tGET_ADDRESS\t\\1
\tmove.b\t({registers['awork1']}),{W}
\tsubx.b\t{W},{A}
\tINVERT_XC_FLAGS
\tENDM

SBC_IMM:MACRO
\tINVERT_XC_FLAGS
\tmove.b\t#\\1,{W}
\tsubx.b\t{W},{A}
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
\tmove.b\t(1,\\1),{registers['dwork1']}
\tlsl.w\t#8,{registers['dwork1']}
\tmove.b\t(\\1),{registers['dwork1']}
\tmove.w\t{registers['dwork1']},\\1
\tENDM

GET_ADDRESS:MACRO
\tlea\t\\1,{registers['awork1']}
\tjbsr\tget_address
\tENDM


""")

    f.write("cpu_init:\n")
    for i in range(8):
        f.write(f"\tmoveq\t#0,d{i}\n")
    f.write("\trts\n\n")

    f.write(f"""get_address:
\t{error}: "`TODO: implement this by adding memory base to {registers['awork1']}"
\trts

""")


buffer = f.getvalue()+"".join(nout_lines)

# remove review flags if requested (not recommended!!)
if cli_args.no_review:
    nout_lines = [line for line in buffer.splitlines(True) if "^ TODO" not in line]
else:
    nout_lines = [line for line in buffer.splitlines(True)]

with open(cli_args.code_output,"w") as f:
    f.writelines(nout_lines)

    f.write(f"""
multiply_ab:
\tand.w\t#{out_hex_sign}FF,{registers['a']}
\tand.w\t#{out_hex_sign}FF,{registers['b']}
\tmulu\t{registers['b']},{registers['a']}
\trts
""")

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




