#
# Z80 to 680x0 converter by JOTD (c) 2023-2026
#
# this is the full refactoring of the tool. Old tool has been renamed to _legacy.py
#
# this code has been successfully used to convert the following games
#
# - Pleiads

# you'll have to implement the macro GET_ADDRESS_FUNC to return pointer on memory layout
# to replace lea/move/... in memory
# extract RAM memory constants as defines, not variables
# works like an emulator
#
# This is a full rewrite based on the 6809 converter, because the old Z80 converter required too
# much manual rewrite, debugging, wrong code. Took a long time to make a small game right
#
# if memory is not banked, it is possible to create a full 64k address space
# and almost leave the code live its life. Just insert some video update commands there
# and there when the game changes tiles or other things
#
# the converter tries to keep A,B and D updated, the result is sometimes it does things
# that aren't really needed. But it's accurate at least and code runs without need for
# complete RE + debug...
#
# what I'm advising is that ONLY AFTER THE CODE WORKS 100%, profile it using MAME trace and scripts
# (there are python scripts that do that in that repository) and concentrate on the 68k code
# in regions where the code is often called, optimize manually, and never re-generate
#
# first version of the refactored code allowed to convert 8085 code and run intro of Pleiads
# with some patching, but mostly the patching was reported by ERROR directives
#
# check how conversion+custom post-processing does an automatic job here:
# https://github.com/jotd666/????
#
#
# limitations:
#
# the main limitation is the inability to stick to the stack model.
#
# TODO

# optims: remove MAKE_HL if H(D5) or L(D6) not changed in between, same for DE/BC
#     MAKE_H then    MAKE_HL => we can remove MAKE_HL / BC / DE
#     remove MAKE_HL after LOAD_HL
# optims: remove tst.b d0 after move.xxx ,d0
#    subq.b    #1,(a0)                             | [$2416: dec (hl)]
#    MAKE_HL                                    | [$2417: ld a,(hl)]  remove make_hl because a0 is already OK
#    move.b    (a0),d0                             | [...]
#
#  .w operation on d6 plus MAKE_H => remove MAKE_HL, replace by MAKE_AR_FROM_HL
# adjust continuation comments which are incorrect at times
# optimize: don't remove MAKE_HL after LOAD_HL, just change by GET_REG_UNCHECKED_ADDRESS 0,d6, and remove from MAKE_HL
# as this could just mean to load a value
#
#  AF88: 21 27 EA    ld   hl,$AE63  => wrong code
#  in the end insert continuation comments when addresses repeat, not when generating

import re,itertools,os,collections,glob,io,pathlib,sys
import argparse
#import simpleeval # get it on pypi (pip install simpleeval)

def remcomments(line):
    return re.sub("[\|\*].*","",line)

def remove_continuing_lines(lines,i):
    for j in range(i+1,i+4):
        if "[...]" in lines[j]:
            lines[j] = ""
        else:
            break


def get_line_address(line):
    try:
        toks = line.split(out_comment)
        address = toks[1].strip(" [$").split(":")[0]
        return int(address,16)
    except (ValueError,IndexError):
        return None

def rebuild_lines(lines):
    return "\n".join(lines).splitlines()

def change_instruction(code,lines,i,continuing_lines=True):
    line = lines[i]
    toks = line.split(out_comment)
    if len(toks)==2:
        toks[0] = f"\t{code}"
        if continuing_lines:
            remove_continuing_lines(lines,i)
        return f" {out_comment} ".join(toks)
    return line


def optimize(lines,verbose=False):
    nb = 0
    prev_loaded = None


##    for i,org_line in enumerate(lines):
##        line = remcomments(org_line)  # remove comments
##        toks = line.split()
##        if toks and "MOVE_W" in toks[0]:
##            prev_line = remcomments(lines[i-1])
##            prev_toks = prev_line.split()
##            if len(prev_toks)==2 and prev_toks[0]=="GET_ADDRESS":
##                try:
##                    address = int(prev_toks[1],16)
##                except ValueError:
##                    address = int(prev_toks[1].split("_")[-1],16)
##                if address%2 == 0:
##                    # even: remove macro use move.w (faster on 68000/68010, no effect on 68020+)
##                    args = toks[1].split(",")
##                    arg = f"{args[0]},({args[1]})" if toks[0]=="MOVE_W_FROM_REG" else f"({args[0]}),{args[1]}"
##                    lines[i] = change_instruction(f"move.w\t{arg}",lines,i,False)


    new_lines = []
    for i,org_line in enumerate(lines):
        line = remcomments(org_line)  # remove comments
        toks = line.split()
        if "GET_ADDRESS" in toks or "GET_UNCHECKED_ADDRESS" in toks:
            value = toks[1]
            if prev_loaded == value and i-prev_line < 6:
                print(f"Prev loaded: {prev_loaded} line {i+1} loaded at line {prev_line+1}")
                org_line = re.sub(".*\|","\t|",org_line)
                nb += 1
            prev_line = i
            prev_loaded = value
        if any(x in toks for x in breaking_instructions) or any(x.startswith("GET_") for x in toks):
            prev_loaded = None
        if re.match("\w+:",line):
            prev_loaded = None


        new_lines.append(org_line)



    if verbose:
        if nb:
            print(f"found {nb} GET_ADDRESS useless occs")
        else:
            print("Nothing found")

    reg16_suffix = ["HL","DE","BC"]

    prev_line = ""
##    # simplify PUSH/MAKE_A/POP/MAKE_D pattern, PUSH/POP are useless in that case
    for i,org_line in enumerate(new_lines):
        line = remcomments(org_line)  # remove comments

        # remove MAKE_HL if follows directly LOAD_HL (because HL.W was changed)
        # or if (a0) is used (means that we have updated HL earlier)
        for rs in reg16_suffix:
            if f"MAKE_AR_FROM_{rs}" in line and any(x in prev_line for x in [f"LOAD_{rs}"]):
                new_lines[i]= ""
                break
        prev_line = line

        if "tst.b" in line.split():
            arg = line.split()[1]
            prev_args = prev_line.split()
            if prev_args and prev_args[-1]==arg:
                new_lines[i] = ""  # remove tst.b if follows op on same register
    # remove empty
    new_lines = [n for n in new_lines if n]

    AW = registers['awork0']
    kill_lines = []
    # remove simple MAKE_AR_xx / (a0) / MAKE_AR_xx sandwich. Not doing the more complex ones
    # hopefully it solves a lot of those
    for i,org_line in enumerate(new_lines):
        line = remcomments(org_line)  # remove comments
        toks = line.split()
        if len(toks)>=2:
            if toks[0].startswith("MAKE_AR") and toks[1]==AW:
                # inspect the above lines
                prev_line = remcomments(new_lines[i-1])
                if AW in prev_line:
                    prev_prev_line = remcomments(new_lines[i-2])
                    ntoks = prev_prev_line.split()
                    if len(ntoks)>=2:
                        if ntoks[0]==toks[0] and ntoks[1]==AW:
                            # mark line for removal, removing it now
                            # would make further detections fail
                            kill_lines.append(i)

    for k in kill_lines:
        new_lines[k]=""
    # remove empty
    new_lines = [n for n in new_lines if n]

    return new_lines

tool_version = "2.1"

asm_styles = ("mit","mot")
parser = argparse.ArgumentParser()
parser.add_argument("-i","--input-mode",help="input mode either mot style (comments: ;, hex: $)\n"
"or mit style (comments *|, hex: 0x",choices=asm_styles,default=asm_styles[1])
parser.add_argument("-o","--output-mode",help="output mode either mot style or mit style",choices=asm_styles
,default=asm_styles[0])
parser.add_argument("-w","--no-review",help="don't insert review lines",action="store_true")
parser.add_argument("-s","--spaces",help="replace tabs by x spaces",type=int)
parser.add_argument("-n","--no-mame-prefixes",help="treat as real source, not MAME disassembly",action="store_true")
parser.add_argument("-l","--label-prefix",help="useful with multiple banks. default 'l_'", default='l_')
parser.add_argument("-c","--code-output",help="68000 source code output file",required=True)
parser.add_argument("-d","--date-check",help="convert only if input file is more recent than output",action="store_true")
parser.add_argument("-O","--optimize",help="remove redundant address loads",action="store_true")
parser.add_argument("-I","--include-output",help="include output file",required=True)
parser.add_argument("input_file")


OPENING_BRACKET = ('(','[')
BRACKETS = "[]()"

cli_args = parser.parse_args()

lab_prefix = cli_args.label_prefix

no_mame_prefixes = cli_args.no_mame_prefixes

cli_args.input_file = pathlib.Path(cli_args.input_file)
cli_args.code_output = pathlib.Path(cli_args.code_output)

if cli_args.input_file.absolute() == cli_args.code_output.absolute():
    raise Exception("Define an output file which isn't the input file")

if cli_args.date_check:
    try:
        if cli_args.input_file.stat().st_mtime < cli_args.code_output.stat().st_mtime:
            print(f"{cli_args.code_output} is newer than {cli_args.input_file}, ignore")
            sys.exit(0)
    except OSError:
        pass

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
    jmp_instruction = "jra"
    branch_prefix = "j"
else:
    out_comment = ";"
    out_start_line_comment = out_comment
    out_hex_sign = "$"
    out_byte_decl = "dc.b"
    out_long_decl = "dc.l"
    jsr_instruction = "jsr"
    jmp_instruction = "jmp"
    branch_prefix = "b"

breaking_instructions = {"rts",jmp_instruction,"bra",jsr_instruction}




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


def warn(m):
    print(f"warning: {m}")

address_re = re.compile("^([0-9A-F]{4}):")
label_re = re.compile("^(\w+):")
error = "ERROR"

# doesn't capture all hex codes properly but we don't care
if no_mame_prefixes:
    instruction_re = re.compile("\s+(\S.*)")
else:
    instruction_re = re.compile("([0-9A-F]{4}):(( [0-9A-F]{2}){1,})\s+(\S.*)")

special_loop_instructions = {"ldi","ldd","lddr","ldir","cpir","cpdr","rld","rrd","cpi","cpd","exx"}
special_loop_instructions_met = set()

addresses_to_reference = set()

address_lines = {}
lines = []
input_files = glob.glob(str(cli_args.input_file))
if not input_files:
    raise Exception(f"{cli_args.input_file}: no match")

for input_file in input_files:
    with open(input_file,"rb") as f:
        if len(input_files)>1:
            lines.append((f"{out_start_line_comment} input file {os.path.basename(input_file)}",False,None))
        prev_address = None
        previous_nb_bytes = None
        instruction = None

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

                        if prev_address:
                            if address < prev_address+previous_nb_bytes:
                                warn(f"instruction overlap at ${address:04x}, prev inst at ${prev_address:04x}, prev len = {previous_nb_bytes} bytes")
                            elif address > prev_address+previous_nb_bytes:
                                itoks = instruction.split()
                                fitok = itoks[0]
                                if fitok.upper() in ["RET","JP","JR","RETI","RST"]:
                                    pass
                                else:
                                    warn(f"instruction discontinuity at ${address:04x}, prev inst at ${prev_address:04x}")
                        previous_nb_bytes = len(m.group(2).split())
                        prev_address = address
                        instruction = m.group(4)

                    address_lines[address] = i
                    txt = instruction.rstrip()
                    is_inst = True
                else:
                    txt = line.rstrip()
            lines.append((txt,is_inst,address))


def issue_warning(msg,newline=False):
    rval =  f'\t{error}\t"at 0x{current_address:04x}: review {msg}"'
    if newline:
        rval += "\n"
    return rval

# convention:
# a => d0
# x => d1
# y => d2
# u => d3

registers = {
"a":"d0","b":"d1","c":"d2","d":"d3","e":"d4","h":"d5","l":"d6",
"ix":"a2",
"iy":"a3",
"dwork1":"d7",
"awork0":"a0",
"awork1":"a1",
"mem_base":"a6",
"sp":"a7",
"":""
}
inv_registers = {v:k.upper() for k,v in registers.items()}
registers_16 = {'hl':registers['l'],'de':registers['e'],'bc':registers['c']}
registers_32 = {'ix':registers['ix'],'iy':registers['iy']}
inv_registers_32 = {v:k for k,v in registers_32.items()}
inv_registers_16 = {v:k.upper() for k,v in registers_16.items()}
inv_registers_16['h'] = 'hl'
inv_registers_16['d'] = 'de'
inv_registers_16['b'] = 'bc'

reg_size = {r:2 for r in registers_16}
reg_size.update({r:1 for r in inv_registers})
reg_size.update({r:4 for r in registers_32.values()})

extra_z80_regs = {"i","r","ixl","ixh","iyl","iyh"}

# inverted (note: C flag is already converted to 68k counterpart at that point hence the access to registers dict
rts_cond_dict = {"c":"jcc",registers["c"]:"jcc","nc":"jcs","z":"jne","nz":"jeq","p":"jmi","m":"jpl","po":"jvc","pe":"jvs"}
# d2 stands for c which has been replaced in a generic pass
jr_cond_dict = {registers["c"]:"jcs","c":"jcs","nc":"jcc","z":"jeq","nz":"jne","p":"jpl","m":"jmi","po":"jvs","pe":"jvc"}

if cli_args.output_mode == "mot":
    # change "j" by "b"
    jr_cond_dict = {k:"b"+v[1:] for k,v in jr_cond_dict.items()}
    rts_cond_dict = {k:"b"+v[1:] for k,v in rts_cond_dict.items()}

rega = registers['a']
single_instructions = {"nop":"nop",
"ret":"rts",
"daa":"DAA",
"scf":"SET_XC_FLAGS",
"ccf":"INVERT_XC_FLAGS",
"neg":f"neg.b\t{rega}",
"cpl":f"not.b\t{rega}",
"ei":"CLR_I_FLAG",
"di":"SET_I_FLAG",
"rra":f"roxr.b\t#1,{rega}",
"rla":f"roxl.b\t#1,{rega}",
"rrca":f"ror.b\t#1,{rega}",
"rlca":f"rol.b\t#1,{rega}"}


AW = registers['awork0']
AW1 = registers['awork1']
DW = registers['dwork1']
MEMBASE = registers['mem_base']

m68_regs = set(registers.values())




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

def get_reg_size(d):
    return reg_size[d]

def decode_2_args(args):
    dest,src = args
    src_is_reg = src in inv_registers or src in registers_16 or src in registers_32
    dest_is_reg = dest in inv_registers or dest in registers_16 or dest in registers_32
    return dest,src,src_is_reg,dest_is_reg

def decode_paren_arg(dest):
    dest = dest.strip("()")
    toks = dest.split(",")
    if len(toks)==1:
        return None,toks[0]
    else:
        return toks

# trying to factorize operations

# sorry for the mess, it's been built progressively without real design
# but it works :)

def generic_load(inst,args,comment):
    rval = ""
    is_move = inst=="move"
    address_reg = AW
    if len(args)==1:
        nargs = [registers['a'],args[0]]
    else:
        nargs = args
    dest,src,src_is_reg,dest_is_reg = decode_2_args(nargs)
    if dest_is_reg:
        op_size = get_reg_size(dest)
        if src_is_reg:
            if src in registers_16:
                rval += f"\tMAKE_{src.upper()}_NO_AR{comment}\n"
                src = registers_16[src]
            if op_size == 1:
                rval += f"\t{inst}.b\t{src},{dest}{comment}"
            elif op_size == 4:
                rval += f"\t{inst}.l\t{src},{dest}{comment}"
            else:
                # dest is 16 bits
                if is_move:
                    rval += "\tLOAD_{dest.upper()}\t{src}{comment}"
                else:
                    d68k = registers_16[dest]
                    s68k = src
                    # src is already converted see above (src is a registers_16)
                    # this is slightly messy!
                    rval += f"""
\tMAKE_{dest.upper()}_NO_AR{comment}
\t{inst}.w\t{s68k},{d68k}{comment}
\tPUSH_SR\t{comment} save CC
\tMAKE_{dest.upper()[0]}\t{comment} update MSB reg
\tPOP_SR\t{comment} restore CC"""

        else:

            if src[0]=='(':
                # in a register, possibly with offset
                offset,reg = decode_paren_arg(src)

                if reg in registers_16:
                    rval += f"\tMAKE_AR_FROM_{reg.upper()}\t{AW}{comment}\n"
            if dest in inv_registers_32:  # a2 or a3 (ix,iy)
                if src[0]=='(':
                    src = src.strip("()")
                    rval += f"\tGET_ADDRESS\t{src},{AW}{comment}\n"
                    rval += f"\tREAD_ADDRESS\t{AW},{dest}{comment}"
                else:
                    rval += f"\tGET_ADDRESS\t{src},{dest}{comment}"  # simple load into address register
            else:
                if src[0]=='(':
                    src = src.strip('()')
                    if reg in inv_registers_32:
                        address_reg = reg
                    elif reg not in registers_16:
                        rval += f"\tGET_ADDRESS\t{reg},{AW}{comment}\n"

                    size = "b"
                    if op_size == 2:
                        size = "w"
                        orig_dest = dest
                        dest = registers_16[dest]
                    targ = f"({offset},{address_reg})" if offset else f"({address_reg})"
                    rval += f"\t{inst}.{size}\t{targ},{dest}{comment}\n"
                    if size=="w":
                        # we just loaded a 16 bit register like HL, DE, we need to update H,D...
                        # else next MAKE_HL will create an incorrect value
                        rval += f"\tMAKE_{orig_dest[0].upper()}{comment}"

                else:
                    if op_size == 1:
                        rval += f"\t{inst}.b\t#{src},{dest}{comment}"
                    else:
                        if is_move:
                            rval += f"\tLOAD_{dest.upper()}\t#{src}{comment}"
                        else:
                            rdest = registers_16[dest]
                            rval += f"\tMAKE_{dest.upper()}_NO_AR{comment}\n\t{inst}.w\t#{src},{rdest}{comment}\n\tMAKE_{dest[0].upper()}"

    else:
        if dest[0]=='(':
            # in a register, possibly with offset
            offset,reg = decode_paren_arg(dest)
            if reg in registers_16:
                rval += f"\tMAKE_AR_FROM_{reg.upper()}\t{AW}{comment}\n"
            elif reg in inv_registers_32:
                # direct access using ix,iy host address
                address_reg = reg
            else:
                # not a register
                rval += f"\tGET_ADDRESS\t{reg},{AW}{comment}\n"

            op_size = "b"
            if src_is_reg:
                src_reg_size = get_reg_size(src)
                if src_reg_size == 2:
                    rval += f"\tMAKE_{src.upper()}_NO_AR{comment}\n"
                    src = registers_16[src]
                    op_size = "w"
                elif src_reg_size == 4:
                    # address register used: we have to convert to word
                    rval += f"\tWRITE_ADDRESS\t{src},{AW}{comment}\n"
                    src = DW
                    op_size = "w"
                source = src
            else:
                source = f"#{src}"

            targ = f"({offset},{address_reg})" if offset else f"({address_reg})"
            if is_move and source[0]=='#' and parse_hex(src,default=None)==0:
                rval += f"\tclr.b\t{targ}{comment}"
            else:
                rval += f"\t{inst}.{op_size}\t{source},{targ}{comment}"


    return rval





def f_call(args,comment):
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
        if cli_args.output_mode == "mot":
            loclab = get_mot_local_label()
            out = f"\t{rts_cond_dict[cond]}\t{loclab}{comment}\n"
        else:
            out = f"\t{rts_cond_dict[cond]}\t0f{comment}\n"

    out += f"\t{jsr_instruction}\t{func}{comment}"
    if len(args)==2:
        if cli_args.output_mode == "mot":
            out += f"\n{loclab}:"
        else:
            out += f"\n0:"
    if target_address is not None:
        add_entrypoint(parse_hex(target_address))
    return out

def f_bit(args,comment):
    return bit_op("btst",args,comment)
def f_set(args,comment):
    return bit_op("bset",args,comment)
def f_res(args,comment):
    return bit_op("bclr",args,comment)

def bit_op(op,args,comment):
    return generic_load(op,args[::-1],comment)

def f_djnz(args,comment):
    target_address = arg2label(args[0])
    if target_address != args[0]:
        add_entrypoint(parse_hex(args[0]))

    # a dbf wouldn't work as d1 loaded as byte and with 1 more iteration
    # adapt manually if needed
    return f"\tsubq.b\t#1,d1\t{comment}\n\tjne\t{target_address}\t{comment}"



def f_ld(args,comment):
    return generic_load('move',args,comment)

def f_dec(args,comment):
    return f_dec_or_inc("subq",args,comment)
def f_inc(args,comment):
    return f_dec_or_inc("addq",args,comment)

def f_dec_or_inc(inst,args,comment):
    return generic_load(inst,[args[0],"1"],comment)

def f_sbc(args,comment):
    return generic_load("subx",args,comment)

def f_adc(args,comment):
    return generic_load("addx",args,comment)


##def f_sbc_or_adc(inst,args,comment):
##    if len(args)==1:
##        # assume A
##        dest = registers["a"]
##        source = args[0]
##    else:
##        dest = args[0]
##        source = args[1]
##    out = ""
##
##    if dest in inv_registers_16:
##        # probably comparison between 2 data registers
##        out = f"\t{inst}.w\t{source},{dest}{comment}\n"+issue_warning("compared/subbed registers")
##
##    elif source in inv_registers:
##        out = f"\t{inst}x.b\t{source},{dest}{comment}"
##    elif is_immediate_value(source):
##        out = f"\t{inst}x.b\t#{source},{dest}{comment}"
##    else:
##        src_strip = source.strip("()")
##        if source.startswith("(") and src_strip in registers_16:
##            out = f"\tMAKE_{src_strip.upper()}\t{AW}{comment}\n"
##            source = f"({AW})"
##        out += f"\t{inst}x.b\t{source},{dest}{comment}"
##    return out



##EX AF,AF'  ; échange le registre AF avec le registre secondaire AF'
##EX HL,DE   ; échange le registres HL avec le registre DE
##EX HL,(SP) ; échange le registre HL avec la dernière valeur stockée dans la pile
##EX IX,(SP) ; échange le registre IX avec la dernière valeur stockée dans la pile
##EX IY,(SP) ; échange le registre IY avec la dernière valeur stockée dans la pile

def f_ex(args,comment):
    arg0,arg1 = args
    dwork = DW
    if arg1.lower() == "af'":
        arg1 = dwork
        if arg0.lower() == "af":
            arg0 = "d0"
    txt = ""
    regsp = f'({registers["sp"]})'

    if arg0 in registers_16 and arg1 in registers_16:
        txt = f"\tMAKE_{arg0.upper()}_NO_AR{comment}\n\tMAKE_{arg1.upper()}_NO_AR{comment}\n"
        arg0 = registers_16[arg0]
        arg1 = registers_16[arg1]
    elif arg1==regsp or arg0==regsp:
        # exchange (a7) with HL/DE/BC: this usually is used to jump
        # but sometimes it's just a save/restore
        if arg0==regsp:
            arg0,arg1=arg1,arg0
            marg0 = registers_16[arg0]
        txt = issue_warning("exchange with (sp)",newline=True)
        txt += f"""\tmove.w\t{regsp},{DW}{comment}
\texg\t{marg0},{DW}{comment}
\tMAKE_{arg0[0].upper()}{comment}
\tmove.w\t{DW},{regsp}{comment}"""
        return txt

    if arg1 == dwork:
        txt += f"\tEXG_AF_AF_PRIME{comment}"
        txt += "\n"+issue_warning("if carry flag not used, replace by EXG_A_A_PRIME")
    else:
        txt += f"\texg\t{arg0},{arg1}{comment}"
    return txt

def f_push(args,comment):
    arg = args[0]
    rval = ""
    if arg in registers_16:
        rval = f"\tMAKE_{arg.upper()}_NO_AR{comment}\n\tmove.w\t{registers_16[arg]},-({registers['sp']}){comment}"
    elif arg == "af":
        # target stack is always even. Push CC first, avoids the use of movem
        rval = f"\tPUSH_SR\t{comment}\n\tmove.w\t{registers['a']},-({registers['sp']}){comment}"
    elif arg in inv_registers and arg.startswith("a"):
        rval = f"\tmove.l\t{arg},-({registers['sp']}){comment}"
    else:
        rval = issue_warning(f"Unsupported push with {arg}")

    return rval

def f_pop(args,comment):
    arg = args[0]
    rval = ""
    if arg in registers_16:
        rval = f"\tmove.w\t({registers['sp']})+,{registers_16[arg]}{comment}\n\tMAKE_{arg[0].upper()}{comment}"
    elif arg == "af":
        rval = f"\tmove.w\t({registers['sp']})+,{registers['a']}{comment}\n\tPOP_SR{comment}"
    elif arg in inv_registers and arg.startswith("a"):
        rval = f"\tmove.l\t({registers['sp']})+,{arg}{comment}"
    else:
        rval = issue_warning(f"Unsupported pop with {arg}")
    return rval

def f_add(args,comment):
    return generic_load("add",args,comment)
def f_sub(args,comment):
    return generic_load("sub",args,comment)

def f_cp(args,comment):
    return generic_load("cmp",args,comment)

def f_and(args,comment):
    # and a special optim
    if args[0]==registers['a']:
        return f"\ttst.b\t{registers['a']}{comment}"

    return generic_load("and",args,comment)
def f_or(args,comment):
    return generic_load("or",args,comment)

def f_xor(args,comment):
    p = args[0]
    if p==registers['a']:
        # optim, as xor a is a way to zero a/clear carry
        out = f"\tCLR_XC_FLAGS{comment}\n\tclr.b\td0{comment}"
    elif is_immediate_value(p):
        out = f"\teor.b\t#{p},d0{comment}"
    else:
        out = ""
        src_strip = p.strip("()")
        if p.startswith("(") and src_strip in registers_16:
            out = f"\tMAKE_{src_strip.upper()}\t{AW}{comment}\n"
            p = f"({AW})"

        out += f"\teor.b\t{p},{registers['a']}{comment}"

    return out

def f_rl(args,comment):
    return f_logical_op("roxl",args,comment)
def f_rr(args,comment):
    return f_logical_op("roxr",args,comment)

def f_rlc(args,comment):
    return f_logical_op("rol",args,comment)
def f_rrc(args,comment):
    return f_logical_op("ror",args,comment)
def f_srl(args,comment):
    return f_logical_op("lsr",args,comment)
def f_sll(args,comment):
    return f_logical_op("lsl",args,comment)
def f_sla(args,comment):
    return f_logical_op("asl",args,comment)
def f_sra(args,comment):
    return f_logical_op("asr",args,comment)

def f_logical_op(op,args,comment):
    return generic_load(op,[args[0],"1"],comment)

def f_ret(args,comment):
    binst = rts_cond_dict[args[0]]
    if cli_args.output_mode == "mit":
        return f"\t{binst}\t0f{comment}\n\trts{comment}\n0:"
    else:
        loclab = get_mot_local_label()
        return f"\t{binst}.b\t{loclab}{comment}\n\trts{comment}\n{loclab}:"

def f_rst(args,comment):
    return f_call(args,comment)

def f_jp(args,comment):
    target_address = None
    if len(args)==1:
        if args[0].startswith("("):
            rval = issue_warning("indirect jump")+comment
            return rval
        else:
            label = arg2label(args[0])
            if args[0] != label:
                # had to convert the address, keep original to reference it
                target_address = args[0]
            jinst = jmp_instruction
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

f_jr = f_jp

def unsupported_instruction(inst,args,comment):
    unknown_instructions.add(inst)
    return issue_warning(f"unknown/unsupported instruction {inst} with args {args}")+comment



def get_substitution_extended_reg(arg):
    if arg == registers['b'] or arg == registers['a']:
    # problem: using .w on B register actually picks D
    # also there's a sign extension to consider!
        rval = f"""\tmoveq\t#0,{DW}{comment}
\tmove.b\t{arg},{DW}{comment} as byte
\tDO_EXTB\t{DW}{comment} with sign extension
"""
        return rval,DW
    else:
        return "",arg



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
current_address = 0

for i,(l,is_inst,address) in enumerate(lines):
    out = ""
    old_out = l
    if is_inst:
        instructions += 1
        # try to convert
        toks = l.split(in_comment,maxsplit=1)
        # add original 6809 instruction
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
        itoks = inst.split()

        if inst in special_loop_instructions:
            special_loop_instructions_met.add(inst)  # note down that it's used

        if len(itoks)==1:
            inst = inst.lower()
            si = single_instructions.get(inst)
            if si:
                out = f"\t{si}{comment}"
            elif inst in special_loop_instructions:
                special_loop_instructions_met.add(inst)  # note down that it's used
                out = f"\t{jsr_instruction}\t{inst}{comment}\n"
            else:
                out = unsupported_instruction(inst,"",comment)

        elif len(itoks)==2:
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
            current_address = address
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
                # warn about manual usage for s register
                # most of the time pshs and puls are used and can be replaced by move/movem+rts
                # but sometimes there can be a mix of pshs and direct access to the stack.
                # as we cannot map the stack on host stack (alignment & size issues) we have 2 stacks
                #
                # sp: host stack: used to store return addresses and pshs args
                # d5: target stack: used to store game "auto" variables. No need to align
                # mixing both stack usages in a routine is a recipe for disaster
                #
                # we have to warn the user systematically when a ",s" is used
                #
                stripped_jargs = [j.strip("+-") for j in jargs]
                if registers['sp'] in stripped_jargs:
                    out = issue_warning("check explicit SP usage",newline=True)+ out
            else:
                if inst.startswith("."):
                    # as-is
                    out = l
                else:
                    out = f"\n"+unsupported_instruction(inst,args,comment)
        else:
            # without this, if a spurious token is present after the instruction, the conversion collates it
            # and it can be incorrect. Lost a few hours because of that in Ghosts'N'Goblins final level bug
            # $ca34: addd   #$0010  10  => add.w    #0x001010,d1 !!!!
            raise Exception(f"Problem parsing: {l}: too many whitespace-separated tokens")
    else:
        out=address_re.sub(rf"{lab_prefix}\1:",l)
        # convert in comments by out comments in label comments (was unsupported)
        if ":" in out and in_comment in out:
            toks = out.split(in_comment)
            out = out_comment.join(toks)

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

def replace_instruction(new_instruction,line):
    comment_pos = line.index(out_comment)
    return new_instruction + " "*(comment_pos-len(new_instruction)) + line[comment_pos:]

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

flag_generating_instructions = {"subq","addq","add","sub","cmp","lsr","lsl","asl","asr","ror","rol","roxr","roxl","subx","addx","abcd","sbcd"}
z_generating_instructions = flag_generating_instructions | {"and","or","tst","btst"}
carry_generating_instructions = flag_generating_instructions | {"CLR_XC_FLAGS","SET_XC_FLAGS"}
conditional_branch_instructions = {"bpl","bmi","bls","bne","beq","bhi","blo","bcc","bcs","blt","ble","bge","bgt"}
conditional_branch_instructions.update({f"j{x[1:]}" for x in conditional_branch_instructions})
routine_call_instructions = {"bsr","jbsr","jsr"}
cmp_instructions = ["cmp.b","CMP_W_TO_REG"]


current_address = 0
for i,line in enumerate(nout_lines):
    current_address = get_line_address(line) or current_address
    comment = f"{out_comment} [${current_address:04x}: "
    line = line.rstrip()
    toks = line.split("|",maxsplit=1)
    if len(toks)==2:
        fp = toks[0].rstrip().split()
        finst = fp[0]

        if finst == "DAA" and prev_fp:
            # try to match add/sub + DAA and replace by abcd
            finst = finst.lower()
            prev_inst = prev_fp[0]
            if prev_inst in ["addx.b","subx.b","add.b","sub.b"]:
                nout_lines[i] = ""
                tmpreg = DW
                clear_xc = f"\tCLR_XC_FLAGS{comment}{finst}]\n" if "addx" not in prev_inst and "subx" not in prev_inst else ""
                new_inst = prev_inst.replace("addx.b","abcd")
                new_inst = new_inst.replace("add.b","abcd")
                new_inst = new_inst.replace("subx.b","sbcd")
                new_inst = new_inst.replace("sub.b","sbcd")
                toks = prev_fp[1].split(",")
                if prev_inst in nout_lines[i-1]:
                    nout_lines[i-1] = f"""{clear_xc}\tmove.b\t{toks[0]},{tmpreg}\t{comment}{finst}]
\t{new_inst}\t{tmpreg},{toks[1]}\t{comment}{finst}]"""
                else:
                    # maybe a label or a comment was inserted there, can't process automatically
                    nout_lines[i] = issue_warning("stray daa, handle manually",newline=True)

##        elif finst == "MAKE_D" and prev_fp and prev_fp[0] == "LOAD_D":
##            # no need to MAKE_D after LOAD_D
##            nout_lines[i] = ""
        elif finst == "rts":
            # if previous instruction sets X flag properly, don't bother, but rol/ror do not!!
            if prev_fp:
                if prev_fp[0] == "movem.l" and "-(sp)" in prev_fp[1]:
                    nout_lines[i] += issue_warning("push to stack+return",newline=True)
                elif prev_fp[0] in cmp_instructions:
                    nout_lines[i] += issue_warning("stray cmp (check caller)",newline=True)

        elif finst in ["addx.b","subx.b","abcd","sbcd"]:
            if fp[1][0]=="#":
                # can't have immediate mode for those, use a work register to make it legal
                src=fp[1].split(",")[0]
                nout_lines[i] = f"\tmove.b\t{src},{DW} {comment}\n"+nout_lines[i].replace(src,DW)
        elif finst not in conditional_branch_instructions and finst != "PUSH_SR" and prev_fp and prev_fp[0] in cmp_instructions:
                nout_lines[i] = issue_warning(f"stray cmp before {finst} (insert SET_X_FROM_C)",newline=True)+nout_lines[i]


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

# specific test for abcd/add/sub sandwich. In ALL games there's a scoring problem because of the way
# the converter post/pre in/decrements registers without systematically pushing/poping SR (because it generally
# isn't useful and wastes cycles). Detect it here

prev_carry_altering_inst = False

nout_lines = rebuild_lines(nout_lines)

current_address=0
for i,line in enumerate(nout_lines):
    current_address = get_line_address(line) or current_address
    toks = line.split()
    if toks:
        inst = toks[0]
        if inst in ["CLR_XC_FLAGS","SET_XC_FLAGS","add.w","sub.w","add.b","sub.b","asl.b","lsr.b","asr.b","lsl.b"] or inst in breaking_instructions:
            # carry won't propagate / is under control by original game code
            prev_carry_altering_inst = False
        elif inst in ["subq.w","addq.w","subq.b","addq.b"]:
            # conversion added increments/decrements which affect X
            # doesn't usually matter except when using carry-based add/subs or BCD'
            prev_carry_altering_inst = True
        elif inst in ["abcd","sbcd","addx.b","subx.b"] and prev_carry_altering_inst:
            nout_lines[i] = issue_warning("subq/addq + abcd/sbcd/subx/addx mix",newline=True)+nout_lines[i]
            prev_carry_altering_inst = False

# try to swap if push_sr and move
prev_inst = None

# remove empty lines ... again, recreate one line per entry
nout_lines = rebuild_lines(nout_lines)


current_address=0
for i,line in enumerate(nout_lines):
    current_address = get_line_address(line) or current_address
    toks = line.split()
    if toks:
        inst = toks[0]

        if inst=="PUSH_SR" and prev_inst == "move.b":
            # code intention is to save registers but move destroys carry
            # so code will probably be wrong. Revert lines and warn
            line += issue_warning("move + push cc had to be swapped, check that it's correct")
            nout_lines[i] = nout_lines[i-1]
            nout_lines[i-1] = line

        prev_inst = inst
    else:
        prev_inst = None
# the generator assumed that rol, ror... a lot of operations can work directly on non-data registers
# for simplicity's sake, now we post-process the generator to insert read to reg/op with reg/write to mem

tmpreg = DW
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
# and trickier remove PUSH_SR / POP_SR block if following
# instruction is not a conditional branch or rts (rts: we don't know how the cc will be used)
prev_line = ""
last_get_address = None
last_dir = None
push_sr_in_block = False

for line in nout_lines_2:
    if label_re.match(line):
        push_sr_in_block = False

    toks = line.split()
    if toks:
        if toks[0] == "PUSH_SR":
            if "POP_SR" in prev_line:
                nout_lines.pop()
                continue
            push_sr_in_block = True
        if toks[0] in ("GET_ADDRESS",):   # do NOT put GET_DP_ADDRESS in list as last optimizer pass needs it
            if last_get_address == toks[1] and last_dir == toks[0]:
                line = remove_instruction(line)
            last_dir = toks[0]
            last_get_address = toks[1]
        elif not toks[0].startswith(("move","add","sub","or","and")):
            # cancel duplicate same get_address call when we're not sure!
            last_get_address = None
        if toks[0] == "nop":
            line = remove_instruction(line)


        if "LOAD_D" in prev_line and toks[0]=="MAKE_D":
            # remove MAKE_D
            continue

    # if move.w in line and (ax) replace move.w by cpu-dependent macro (68000 doesn't appreciate
    # odd read/write on 16 bit
    inst_part = line.split(out_comment)[0]
    if "move.w" in inst_part and f"({AW})" in inst_part:
        if ",(" in inst_part:
            inst = "MOVE_W_FROM_REG"
        else:
            inst = "MOVE_W_TO_REG"
        line = line.replace("move.w",inst).replace(f"({AW})",AW).replace(f"({AW})".lower(),AW)

    for i in ["cmp","add","sub"]:
        if f"{i}.w" in line and f"({AW})" in line:
            inst = f"{i.upper()}_W_TO_REG"
            line = line.replace(f"{i}.w",inst).replace(f"({AW})",AW).replace(f"({AW})".lower(),AW)

    # optimize move.b => clr.b
    line = line.replace("move.b\t#0,","clr.b\t")
    nout_lines.append(line)
    prev_line = line

current_address=0
# another pass after ror has been resolved
for i,line in enumerate(nout_lines):
    current_address = get_line_address(line) or current_address
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
                    # also consider that jsr + jcc/jcs/jne/jeq is not a problem. A lot of programs use C flag as return code
                    # consider that rts+jcc isn't a problem, converting jp cc,label does that.
                    if (inst_no_size != "rts" and inst_no_size not in carry_generating_instructions and
                    inst_no_size not in conditional_branch_instructions and inst_no_size not in routine_call_instructions):
                        if not follows_sr_protected_block(nout_lines,i):
                            nout_lines[i] += issue_warning(f"stray {finst} test after {prev_fp[0]}",newline=True)
            elif finst in ("bne","beq","jne","jeq"):
                if prev_fp:
                    inst_no_size = prev_fp[0].split(".")[0]
                    # also consider that jsr + jcc is not a problem. A lot of programs use C flag as return code
                    # consider that rts+jcc isn't a problem, converting jp cc,label does that.
                    if (inst_no_size != "rts" and inst_no_size not in z_generating_instructions and
                    inst_no_size not in conditional_branch_instructions and inst_no_size not in routine_call_instructions):
                        if not follows_sr_protected_block(nout_lines,i):
                            nout_lines[i] += issue_warning(f"stray {finst} test after {prev_fp[0]}",newline=True)
        prev_fp = fp
        if re.search("GET_.*_ADDRESS",toks[0]) and follows_sr_protected_block(nout_lines,i):
            if i>3 and "PUSH_SR" in nout_lines[i-3]:
                # PUSH/op/POP+GET_xxx_ADDRESS
                # no need to protect CCs as there's a GET_xxx_ADDRESS (so not a test) just after it
                nout_lines[i-1] = ""
                nout_lines[i-3] = ""


optimize_dp = True


# now insert continuation comments

prev_address = None
for i,line in enumerate(nout_lines):
    address = get_line_address(line)
    if address is not None:
        if prev_address == address:
            # convert address comment to [...]
            line = re.sub(f"\[\${address:04x}.*?\]","[...]",line)
            nout_lines[i] = line
        else:
            prev_address = address


if cli_args.spaces:
    nout_lines = [tab2space(n) for n in nout_lines]


f = io.StringIO()

if True:
    A = registers['a']
    B = registers['b']
    C = registers['c']
    D = registers['d']
    E = registers['e']
    H = registers['h']
    L = registers['l']
    IX = registers['ix']
    IY = registers['iy']

    f.write(f"""{out_start_line_comment} Converted with z80to68k v{tool_version} by JOTD
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


\t.macro\tERROR\targ
\t.error\t"\\arg"     | comment out or replace by ".warning" to disable errors
\t.endm

\t.macro\tVIDEO_BYTE_DIRTY
\t{out_comment} called when a byte write was done in {AW}
\t.endm

\t.macro\tVIDEO_WORD_DIRTY
\t{out_comment} called when a word write was done in {AW}
\t.endm

* the function that accesses all memory (except banks)
* without any check
\t.macro\tGET_UNCHECKED_ADDRESS_FUNC\tdest
\tlea\t({MEMBASE},\\dest\\().l),\\dest
\t.endm

\t.macro\tWRITE_ADDRESS\tsrc,dest
\tmove.l\t\\src,{DW}
\tsub.l\t{MEMBASE},{DW}
\tMOVE_W_FROM_REG\t{DW},\\dest
\t.endm

\t.macro\tREAD_ADDRESS\tsrc,dest
\tMOVE_W_TO_REG\ta0,{DW}
\tGET_ADDRESS_FUNC\t{DW}
\tmove.l\t{DW},\\dest
\t.endm

* only in dev mode, else call GET_UNCHECKED_ADDRESS_FUNC
\t.macro\tGET_ADDRESS_FUNC\tdest
\texg\t{AW},\\dest
\t{jsr_instruction}\tget_address
\texg\t{AW},\\dest
\t.endm

\t.macro\tCHECK_MAX\treg,arg
\tERROR  "insert check max table function index here"
\t.endm

\t.macro\tMAKE_AR_FROM_HL\tdest
\tGET_REG_ADDRESS\t0,{L},\\dest
\t.endm
\t.macro\tMAKE_AR_FROM_DE\tdest
\tGET_REG_ADDRESS\t0,{E},\\dest
\t.endm
\t.macro\tMAKE_AR_FROM_BC\tdest
\tGET_REG_ADDRESS\t0,{C},\\dest
\t.endm

\t.macro\tMAKE_HL_NO_AR
{out_start_line_comment} add {H} as MSB of {L} so {L}.W = HL, load target reg
\trol.w\t#8,{L}
\tmove.b\t{H},{L}
\trol.w\t#8,{L}
\t.endm

\t.macro\tMAKE_HL\tdest
\tMAKE_HL_NO_AR
\tMAKE_AR_FROM_HL\t\\dest
\t.endm

\t.macro\tMAKE_H
{out_start_line_comment} update {H} from {L}.W = HL
\trol.w\t#8,{L}
\tmove.b\t{L},{H}
\trol.w\t#8,{L}
\t.endm

\t.macro\tMAKE_BC_NO_AR
{out_start_line_comment} add {B} as MSB of {C} so {C}.W = BC
\trol.w\t#8,{C}
\tmove.b\t{B},{C}
\trol.w\t#8,{C}
\t.endm

\t.macro\tMAKE_BC\tdest
\tMAKE_BC_NO_AR
\tMAKE_AR_FROM_BC\t\\dest
\t.endm

\t.macro\tMAKE_B
{out_start_line_comment} update {B} from {C}.W = HL
\trol.w\t#8,{C}
\tmove.b\t{C},{B}
\trol.w\t#8,{C}
\t.endm

\t.macro\tMAKE_DE_NO_AR
{out_start_line_comment} add {D} as MSB of {E} so {E}.W = DE
\trol.w\t#8,{E}
\tmove.b\t{D},{E}
\trol.w\t#8,{E}
\t.endm

\t.macro\tMAKE_DE\tdest
\tMAKE_DE_NO_AR
\tMAKE_AR_FROM_DE\t\\dest
\t.endm

\t.macro\tMAKE_D
{out_start_line_comment} update {D} from {E}.W = HL
\trol.w\t#8,{E}
\tmove.b\t{E},{D}
\trol.w\t#8,{E}
\t.endm

\t.macro\tLOAD_HL\targument
\tmove.w\t\\argument,{L}
\tMAKE_H
\t.endm

\t.macro\tLOAD_BC\targument
\tmove.w\t\\argument,{C}
\tMAKE_B
\t.endm

\t.macro\tLOAD_DE\targument
\tmove.w\t\\argument,{E}
\tMAKE_D
\t.endm

\t.macro CLR_XC_FLAGS
\tand.b\t#0xEE,ccr\t| bit 4 = X, bit 0 = C
\t.endm

\t.macro SET_XC_FLAGS
\tor.b\t#0x11,ccr\t| bit 4 = X, bit 0 = C
\t.endm


\t.macro INVERT_XC_FLAGS
\teor.b\t#0x11,ccr
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

* useful to store X from C (store cmp result)
\t.macro\tSET_X_FROM_C
\tPUSH_SR
\tmove.w\t(sp),{DW}
\tbset\t#4,{DW}   | set X
\tbtst\t#0,{DW}
\tbne.b\t0f
\tbclr\t#4,{DW}   | C is clear: clear X
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

\t.ifdef\tMC68020


* 68020 compliant & optimized

    .macro    JXX_X_INDEXED    inst,reg,nb_cases,ab
    moveq    #0,{DW}
    move.b    \\ab,{DW}  | mask 8 bits
    CHECK_MAX    {DW},\\nb_cases
    \\inst    ([\\reg,{DW}.W*2])
    .endm


\t.macro DO_EXTB\treg
\textb.l\t\\reg
\t.endm

\t.macro PUSH_SR
\tmove.w\tccr,-(sp)
\t.endm





\t.else

* 68000 compliant

\t.macro    JXX_X_INDEXED    inst,reg,nb_cases,ab
\tmoveq    #0,{DW}   | scratch register
\tmove.b   \\ab,{DW}  | mask 8 bits
\tCHECK_MAX    {DW},\\nb_cases
\t* original register is not changed (could cause issues)
\tadd.w    d6,d6    | *2 (16 -> 32 bits)
\tmove.l    (\\reg,{DW}.w),\\reg
\t\inst    (\\reg)
\t.endm



\t.macro DO_EXTB\treg
\text\t\\reg
\text.l\t\\reg
\t.endm

\t.macro PUSH_SR
\tmove.w\tsr,-(sp)
\t.endm



\t.endif

* same for 68000 and 68020+
\t.macro POP_SR
\tmove.w\t(sp)+,ccr
\t.endm

\t.macro    MOVE_W_TO_REG    src,dest
\tmove.b\t(\\src),\\dest
\trol.w\t#8,\\dest
\tmove.b\t(1,\\src),\\dest
\t.endm

\t.macro\tMOVE_W_FROM_REG    src,dest
\tmove.b\t\\src,(\\dest)
\trol.w\t#8,\\src
\tmove.b\t\\src,(1,\\dest)
\trol.w\t#8,\\src
\t.endm


    .macro    JXX_A_INDEXED    inst,reg,nb_cases
    JXX_X_INDEXED    \\inst,\\reg,\\nb_cases,{A}
    .endm

    .macro    JXX_B_INDEXED    inst,reg,nb_cases
    JXX_X_INDEXED    \\inst,\\reg,\\nb_cases,{B}
    .endm

    .macro    JSR_A_INDEXED    reg,nb_cases
    JXX_A_INDEXED\tjsr,\\reg,\\nb_cases
    .endm
    .macro    JMP_A_INDEXED    reg,nb_cases
    JXX_A_INDEXED\tjmp,\\reg,\\nb_cases
    .endm
    .macro    JSR_B_INDEXED    reg,nb_cases
    JXX_B_INDEXED\tjsr,\\reg,\\nb_cases
    .endm
    .macro    JMP_B_INDEXED    reg,nb_cases
    JXX_B_INDEXED\tjmp,\\reg,\\nb_cases
    .endm

\t.macro\tEXG_A_A_PRIME
\tmove.b\taprime,{DW}       | retrieve A'
\tmove.b\t{A},aprime            | save A
\tmove.b\t{DW},{A}           | A <= A'
\t.endm

\t.macro\tEXG_AF_AF_PRIME
\tPUSH_SR                       | push ccr
\tEXG_A_A_PRIME
\tmove.w\tfprime,{DW}       | retrieve F'
\tmove.w\t(sp),fprime           | save F
\tmove.w\t{DW},(sp)         | F' <= F
\tPOP_SR                        | pop ccr
\t.endm
""")
        for unchecked in ["","UNCHECKED_"]:
            f.write(f"""\t.macro GET_REG_{unchecked}ADDRESS\toffset,reg,dest
\t.ifeq\t\\offset
\tmove.l\t\\reg,\\dest
\t.else
\tlea\t\\offset,\\dest
\tlea\t(\\dest,\\reg\\().l),\\dest
\t.endif
\tGET_{unchecked}ADDRESS_FUNC\t\\dest
\t.endm



\t.macro GET_{unchecked}ADDRESS\toffset,dest
\t.if \\offset=={IX}
    move.l    \\offset,\\dest
    .else
    .if \offset=={IY}
       move.l  \\offset,\\dest
    .else
    lea    \\offset,\\dest
    .endif
    .endif
\tGET_{unchecked}ADDRESS_FUNC\t\\dest
\t.endm

\t.macro GET_INDIRECT_{unchecked}ADDRESS\toffset,dest
\tGET_ADDRESS\t\\offset,\\dest
\tREAD_BE_WORD\t\\dest
\tGET_{unchecked}ADDRESS_FUNC\t\\dest
\t.endm
""")
    else:
        # MOT macros are not up to date for now
        f.write(f"""SBC_X:MACRO
\tINVERT_XC_FLAGS
\tGET_ADDRESS\t\\1
\tmove.b\t({awork0},{X}.w),{DW}
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

POP_SR:MACRO
\tmove.w\t(sp)+,ccr
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

\t.else
PUSH_SR:MACRO
\tmove.w\tsr,-(sp)
\tENDM
POP_SR:MACRO
\tmove.w\t(sp)+,ccr
\tENDM
\tENDC

READ_LE_WORD:MACRO
\tmove.b\t(1,\\1),{DW}
\tlsl.w\t#8,{DW}
\tmove.b\t(\\1),{DW}
\tmove.w\t{DW},\\1
\tENDM

GET_ADDRESS:MACRO
\tlea\t\\1,{AW}
\tGET_ADDRESS_FUNC
\tENDM


""")
    f.write("* zero all registers\n")
    f.write("cpu_init:\n")
    for i in range(8):
        reg = f"d{i}"
        f.write(f"\tmoveq\t#0,{reg}\n")
    f.write(f"\tsub.l\t{IX},{IX}\n")
    f.write(f"\tsub.l\t{IY},{IY}\n")
    f.write("\trts\n\n")

    f.write(f"""get_address:
\t{error} "first check dest in {AW} in dev mode"
\tGET_UNCHECKED_ADDRESS_FUNC\t{AW}
\trts


""")

if os.path.exists(cli_args.include_output):
    print(f"Skipping already created file {cli_args.include_output}")
else:
    print(f"Generating file {cli_args.include_output}")
    with open(cli_args.include_output,"w") as fw:
        fw.write(f.getvalue())
        # TODO: EXX
        A =registers['a']
        B =registers['b']
        fw.write(f"""
""")

buffer = f"""\t.include "{cli_args.include_output}"

"""+"".join(nout_lines)

# remove review flags if requested (not recommended!!)
if cli_args.no_review:
    nout_lines = [line for line in buffer.splitlines(True) if not line.startswith(f"\t{error}")]
else:
    nout_lines = [line for line in buffer.splitlines(True)]


if cli_args.output_mode and cli_args.optimize:
    # can optimize
    print("Optimization phase")
    nout_lines = optimize(nout_lines)

with open(cli_args.code_output,"w") as f:
    f.writelines(nout_lines)

##    f.write(f"""{out_start_line_comment} < D0: byte possibly containing lowernibble > 9
##{out_start_line_comment} > D0: value corrected to full BCD
##daa:
##    move.w    d1,-(a7)
##    move.b    d0,d1
##    and.w    #{out_hex_sign}F,d1
##    sub.b    #10,d1
##    bcs.b    daa_out        | no need to do anything
##    * D1 = A-F: correct
##    add.b    #{out_hex_sign}16,d0
##daa_out:
##    move.w    (a7)+,d1
##    rts
##""")

    if "rld" in special_loop_instructions_met:
        f.write(f"""
{out_start_line_comment} < A0 (HL)
{out_start_line_comment} < D0 (A)
rld:
    movem.w    d1/d2,-(a7)
    move.b    d0,d1        {out_comment} backup A
    clr.w    d2            {out_comment} make sure high bits of D2 are clear
    move.b    ({AW}),d2       {out_comment} read (HL)
    and.b #{out_hex_sign}F,d1        {out_comment} keep 4 lower bits of A
    lsl.w    #4,d2       {out_comment} make room for 4 lower bits
    or.b    d1,d2        {out_comment} insert bits
    move.b    d2,({AW})        {out_comment} update (HL)
    lsr.w    #8,d2        {out_comment} get 4 shifted bits of (HL)
    and.b    #{out_hex_sign}F0,d0    {out_comment} keep only the 4 highest bits of A
    or.b    d2,d0        {out_comment} insert high bits from (HL) into first bits of A
    movem.w    (a7)+,d1/d2
    rts

""")

    if "rrd" in special_loop_instructions_met:
        f.write(f"""
{out_start_line_comment} < A0 (HL)
{out_start_line_comment} < D0 (A)
rrd:
    movem.w    d1/d2,-(a7)
    move.b    d0,d1        {out_comment} backup A
    clr.w    d2            {out_comment} make sure high bits of D2 are clear
    move.b    ({AW}),d2        {out_comment} read (HL)
    and.b    #{out_hex_sign}F,d1        {out_comment} keep 4 upper bits of A
    lsl.b    #4,d1
    ror.w    #4,d2        {out_comment} make room for 4 higher bits
    or.b    d1,d2        {out_comment} insert bits
    move.b    d2,({AW})        {out_comment} update (HL)
    rol.w    #4,d2        {out_comment} get 4 shifted bits of (HL)
    and.b    #{out_hex_sign}F,d2
    and.b    #{out_hex_sign}F0,d0    {out_comment} keep only the 4 highest bits of A
    or.b    d2,d0        {out_comment} insert lowest bits from (HL) into first bits of A
    movem.w    (a7)+,d1/d2
    rts

""")
    if "ldd" in special_loop_instructions_met:
        f.write(f"""
{out_start_line_comment} < A0: source (HL)
{out_start_line_comment} < A1: destination (DE)
{out_start_line_comment} < D1: decremented (16 bit)
ldd:
    MAKE_BC_NO_AR
    move.b    ({AW}),({AW1})
    subq.w  #1,{AW}
    subq.w  #1,{AW1}
    subq.w    #1,{C}
    rts
""")
    if "lddr" in special_loop_instructions_met:
        f.write(f"""
{out_start_line_comment} < A0: source (HL)
{out_start_line_comment} < A1: destination (DE)
{out_start_line_comment} < D1: decremented (16 bit)
lddr:
    MAKE_BC_NO_AR
    subq.w    #1,{C}
    addq.w  #1,{L}
    LOAD_HL {AW}
    addq.w  #1,{E}
    LOAD_DE {AW1}
""")
        if cli_args.output_mode == "mit":
            f.write(f"""0:
    move.b    -({AW}),-({AW1})
    dbf        {C},0b
""")
        else:
            f.write(f""".loop:
    move.b    -({AW}),-({AW1})
    dbf        {C},.loop
""")
        f.write(f"""
    subq.w  #1,{AW1}
    subq.w  #1,{AW}
    moveq\t#0,{C}
    rts
""")
    if "ldi" in special_loop_instructions_met:
        f.write(f"""
{out_start_line_comment} < A0: source (HL)
{out_start_line_comment} < A1: destination (DE)
{out_start_line_comment} < D1: decremented (16 bit)
ldi:
    MAKE_BC_NO_AR
    MAKE_DE_NO_AR
    MAKE_HL_NO_AR
    addq.w    #1,{L}
    addq.w    #1,{E}
    MAKE_AR_FROM_HL\t{AW}
    MAKE_AR_FROM_DE\t{AW1}
    move.l    {AW},{AW1}
    move.b    (-1,{AW}),(-1,{AW1})
    subq.w    #1,{C}
    rts
""")

    if "ldir" in special_loop_instructions_met:
        f.write(f"""
{out_start_line_comment} < A0: source (HL)
{out_start_line_comment} < A1: destination (DE)
{out_start_line_comment} < D1: length (16 bit)
ldir:
    MAKE_BC_NO_AR
    MAKE_HL_NO_AR
    MAKE_DE_NO_AR
    MAKE_AR_FROM_HL\t{AW}
    MAKE_AR_FROM_DE\t{AW1}
    subq.w    #1,{C}
""")
        if cli_args.output_mode == "mit":
            f.write(f"""0:
    move.b    ({AW})+,({AW1})+
    dbf        {C},0b
    moveq\t#0,{C}
    rts
""")
        else:
            f.write(f""".loop:
    move.b    ({AW})+,({AW1})+
    dbf        {C},.loop
    moveq\t#0,{C}
    rts
""")



    if "cpir" in special_loop_instructions_met:
        f.write(f"""
{out_start_line_comment} < A0: source (HL)
{out_start_line_comment} < D1: length to search
{out_start_line_comment} > D0.B value searched for (A)
{out_start_line_comment} > Z flag if found
cpir:
    MAKE_BC_NO_AR
    MAKE_HL
    subq.w    #1,{C}
""")
        if cli_args.output_mode == "mit":
            f.write(f"""0:
    cmp.b    ({AW})+,{A}
    beq.b    1f
    dbf        {C},0b
    moveq\t#0,{C}
    {out_start_line_comment} not found: unset Z
    cmp.b   #1,{C}
1:
    rts
""")
        else:
            f.write(""".loop:
    cmp.b    ({AW})+,d0
    beq.b    .out
    dbf        {C},.loop
    moveq\t#0,{C}
    {out_start_line_comment} not found: unset Z
    cmp.b   #1,{C}
.out:
    rts
""")

    if "cpi" in special_loop_instructions_met:
        f.write(f"""
{out_start_line_comment} < source (HL)
{out_start_line_comment} < B: decremented
{out_start_line_comment} > A: value searched for
{out_start_line_comment} > Z flag if found
{out_start_line_comment}
cpi:
    MAKE_BC_NO_AR
    subq.w    #1,{C}
    MAKE_B
    MAKE_HL_NO_AR
    addq.w   #1,{L}
    MAKE_H
    MAKE_AR_FROM_HL\t{AW}
    cmp.b    (-1,{AW}),{A}
    rts
""")

    if "cpd" in special_loop_instructions_met:
        f.write(f"""
{out_start_line_comment} < HL: source
{out_start_line_comment} < BC: decremented
{out_start_line_comment} > A: value searched for
{out_start_line_comment} > Z flag if found
{out_start_line_comment} careful: d1 overflow not emulated
cpd:
    MAKE_BC_NO_AR
    subq.w    #1,{C}
    MAKE_B
    MAKE_HL_NO_AR
    subq.w   #1,{L}
    MAKE_H
    MAKE_AR_FROM_HL\t{AW}
    cmp.b    ({AW}),{A}
    rts
""")

    if "exx" in special_loop_instructions_met:
        regs = "d1-d4/a0/a1/a4"
        regs_size = 7*4
        f.write(f"""
{out_start_line_comment} < all registers {regs}
{out_start_line_comment} > all registers swapped
{out_start_line_comment}: note regscopy must be defined somewhere in RAM
{out_start_line_comment}: with a size of {regs_size*2}
exx:
\tmove.l\ta6,-(a7)
    lea     regscopy+28,a6
    {out_start_line_comment} save current regs in region 1
    movem.l {regs},-(a6)
    {out_start_line_comment} restore old regs from region 2
    lea     regscopy+28,a6
    movem.l (a6),{regs}
    {out_start_line_comment} now copy region 1 to region 2
    movem.l {regs},-(a7)
    lea     regscopy,a6
    movem.l (a6)+,{regs}
    movem.l {regs},(a6)
    movem.l (a7)+,{regs}
\tmove.l\t(a7)+,a6
    rts
""")
    if "cpdr" in special_loop_instructions_met:
        f.write(f"""
{out_start_line_comment} < A0: source (HL)
{out_start_line_comment} < D1: length to search
{out_start_line_comment} > D0.B value searched for (A)
{out_start_line_comment} > Z flag if found
cpdr:
    subq.w    #1,d1
""")
        if cli_args.output_mode == "mit":
            f.write(f"""0:
    illegal
    subq.w  #1,a0
    cmp.b    (1,a0),d0
    beq.b    1f
    dbf        d1,0b
    clr.w    d1
    {out_start_line_comment} not found: unset Z
    cmp.b   #1,d1
1:
    rts
""")
        else:
            f.write(""".loop:
    subq.w  #1,a0
    cmp.b    (1,a0),d0
    beq.b    .out
    dbf        d1,.loop
    clr.w    d1
    {out_start_line_comment} not found: unset Z
    cmp.b   #1,d1
.out:
    rts
""")


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




