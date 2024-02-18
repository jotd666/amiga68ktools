
# TODO:
#add.b immediate + daa => abcd d7,xx + review
#adc.b + daa => abcd d7,xx aussi!
#ld  bc,imm => issue a "review pick one", issue D1/D2 AND D1.W
#Label_ =  for  jump marks
#Mem_ = memory addresses
# HL referenced then add/sub L => use A0 instead of D6


import re,itertools,os,collections,glob
import argparse
import simpleeval # get it on pypi (pip install simpleeval)

asm_styles = ("mit","mot")
parser = argparse.ArgumentParser()
parser.add_argument("-i","--input-mode",help="input mode either mot style (comments: ;, hex: $)\n"
"or mit style (comments *|, hex: 0x",choices=asm_styles,default=asm_styles[1])
parser.add_argument("-o","--output-mode",help="output mode either mot style or mit style",choices=asm_styles
,default=asm_styles[0])
parser.add_argument("-s","--spaces",help="replace tabs by x spaces",type=int)
parser.add_argument("-n","--no-mame-prefixes",help="treat as real source, not MAME disassembly",action="store_true")
parser.add_argument("--use-bc-as-pointer",help="bc will be saved/restored as address register as well")
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

special_loop_instructions = {"ldi","ldd","lddr","ldir","cpir","cpdr","rld","rrd","cpi","cpd","exx"}
special_loop_instructions_met = set()

##for s,r in regexes_1:
##    try:
##        regexes.append((re.compile(s,re.IGNORECASE|re.MULTILINE),r))
##    except re.error as e:
##        raise Exception("{}: {}".format(s,e))

address_re = re.compile("^([0-9A-F]{4}):",flags=re.I)
# doesn't capture all hex codes properly but we don't care
if no_mame_prefixes:
    instruction_re = re.compile("\s+(\S.*)")
else:
    instruction_re = re.compile("([0-9A-F]{4}):( [0-9A-F]{2}){1,}\s+(\S.*)",flags=re.I)

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
# after scf, carry & X is set
#
# (useful because push/pop af isn't emulated properly, it would involve R/W of 68000 SR
# or 68020 CCR registers and would make that complex to port/would require supervisor mode,
# or would need to call the protected code from a TRAP to make it transparent)

# Galaxian compute_tangent function had to be adapted for this

def allow_upper(d):
    for k,v in tuple(d.items()):
        d[k.upper()] = v

registers = {
"a":"d0","b":"d1","c":"d2","d":"d3","e":"d4","h":"d5","l":"d6","ix":"a2","iy":"a3","hl":"a0","de":"a1","bc":"a4"}  #,"d":"d3","e":"d4","h":"d5","l":"d6",

allow_upper(registers)

inv_registers = {v:k for k,v in registers.items()}


addr2data = {"a4":"d1/d2","a1":"d3/d4"}
addr2data_single = {"a1":"d3","a0":"d5","a4":"d1"}
data2addr_msb = {v:k for k,v in addr2data_single.items()}
data2addr_lsb = {"d4":"a1","d6":"a0","d2":"a4"}
addr2data_lsb = {v:k for k,v in data2addr_lsb.items()}

a_instructions = {"neg":"neg.b\t","cpl":"not.b\t","rra":"roxr.b\t#1,",
                    "rla":"roxl.b\t#1,","rrca":"ror.b\t#1,","rlca":"rol.b\t#1,"}
single_instructions = {"nop":"nop","ret":"rts",
"scf":"SET_XC_FLAGS",
"ccf":"INVERT_XC_FLAGS"}

m68_regs = set(registers.values())
m68_data_regs = {x for x in m68_regs if x[0]=="d"}
m68_address_regs = {x for x in m68_regs if x[0]=="a"}

# inverted (note: C flag is already converted to 68k counterpart at that point hence the access to registers dict
rts_cond_dict = {"c":"bcc",registers["c"]:"bcc","nc":"bcs","z":"bne","nz":"beq","p":"bmi","m":"bpl","po":"bvc","pe":"bvs"}
# d2 stands for c which has been replaced in a generic pass
jr_cond_dict = {registers["c"]:"jcs","c":"jcs","nc":"jcc","z":"jeq","nz":"jne","p":"jpl","m":"jmi","po":"jvs","pe":"jvc"}

if cli_args.output_mode == "mot":
    # change "j" by "b"
    jr_cond_dict = {k:"b"+v[1:] for k,v in jr_cond_dict.items()}



allow_upper(rts_cond_dict)
allow_upper(jr_cond_dict)

lab_prefix = "l_"

def add_entrypoint(address):
    addresses_to_reference.add(address)

def parse_hex(s,default=None):
    is_hex = s.startswith(("$","0x","0X"))
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



def f_djnz(args,comment):
    target_address = arg2label(args[0])
    if target_address != args[0]:
        add_entrypoint(parse_hex(args[0]))

    # a dbf wouldn't work as d1 loaded as byte and with 1 more iteration
    # adapt manually if needed
    return f"\tsubq.b\t#1,d1\t{out_comment} [...]\n\tjne\t{target_address}\t{comment}"



def f_rst(args,comment):
    """ generates a function name that the user has to code
    """
    arg = parse_hex(args[0])
    return f"\tjbsr\trst_{arg:02x}{comment}"

def f_bit(args,comment):
    return f"\tbtst.b\t#{args[0]},{args[1]}{comment}"
def f_set(args,comment):
    return f"\tbset.b\t#{args[0]},{args[1]}{comment}"
def f_res(args,comment):
    return f"\tbclr.b\t#{args[0]},{args[1]}{comment}"

def f_ex(args,comment):
    arg0,arg1 = args
    if arg1.lower() == "af'":
        arg1 = "d7"
        if arg0.lower() == "af":
            arg0 = "d0"

    txt = f"\texg\t{arg0},{arg1}{comment}"
    if arg1 == "d7":
        txt += "\n         ^^^ TODO review: carry flags used below? if so, adapt"
    return txt
def f_push(args,comment):
    reg = args[0]
    block_areg = False
    if not cli_args.use_bc_as_pointer:
        zreg = inv_registers.get(reg)
        if zreg == "bc":
            block_areg = True

    dreg = addr2data.get(reg)
    rval = ""
    # play it safe, we don't know what the program needs
    # address or data, but special case for BC (option)
    if dreg:
        rval = f"\tmovem.w\t{dreg},-(sp){comment}"
    if args[0]=="af":
        rval = f"\tmove.w\td0,-(sp){comment}"
    elif not block_areg:
        if args[0].startswith("a"):
            rval += f"\n\tmove.l\t{args[0]},-(sp){comment}"
        else:
            rval = f"\tmove.w\t{args[0]},-(sp){comment}"
    return rval

def f_pop(args,comment):
    reg = args[0]
    block_areg = False
    if not cli_args.use_bc_as_pointer:
        zreg = inv_registers.get(reg)
        if zreg == "bc":
            block_areg = True
    rval = ""
    if reg=="af":
        rval = f"\tmove.w\t(sp)+,d0{comment}"
    elif not block_areg:
        if reg.startswith("a"):
            rval = f"\tmove.l\t(sp)+,{reg}{comment}"
        else:
            rval = f"\tmove.w\t(sp)+,{reg}{comment}"
    dreg = addr2data.get(reg)
    if dreg:
        rval += f"\n\tmovem.w\t(sp)+,{dreg}{comment}"

    return rval



def f_rl(args,comment):
    arg = args[0]
    return f"\troxl.b\t#1,{arg}{comment}"

def f_rlc(args,comment):
    arg = args[0]
    return f"\trol.b\t#1,{arg}{comment}"

def f_rr(args,comment):
    arg = args[0]
    return f"\troxr.b\t#1,{arg}{comment}"

def f_srl(args,comment):
    arg = args[0]
    return f"\tlsr.b\t#1,{arg}{comment}"

def f_sra(args,comment):
    arg = args[0]
    return f"\tasr.b\t#1,{arg}{comment}"

def f_sll(args,comment):
    arg = args[0]
    return f"\tlsl.b\t#1,{arg}{comment}"

def f_sla(args,comment):
    arg = args[0]
    return f"\tasl.b\t#1,{arg}{comment}"

def f_rrc(args,comment):
    arg = args[0]
    return f"\tror.b\t#1,{arg}{comment}"

def f_ret(args,comment):
    binst = rts_cond_dict[args[0]]
    if cli_args.output_mode == "mit":
        return f"\t{binst}.b\t0f{out_comment} [...]\n\trts{comment} [...]\n0:"
    else:
        loclab = get_mot_local_label()
        return f"\t{binst}.b\t{loclab}{out_comment} [...]\n\trts{comment} [...]\n{loclab}:"

def f_jp(args,comment):
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

def f_xor(args,comment):
    p = args[0]
    if p=="d0":
        # optim, as xor a is a way to zero a/clear carry
        out = f"\tclr.b\td0{comment}"
    elif is_immediate_value(p):
        out = f"\teor.b\t#{p},d0{comment}"
    elif p in m68_data_regs:
        out = f"\teor.b\t{p},d0{comment}"
    else:
        out = f"\tmove.b\t{p},d7\n\teor.b\td7,d0{comment}"
    return out

def f_or(args,comment):
    p = args[0]
    out = None

    if is_immediate_value(p):
        out = f"\tor.b\t#{p},d0{comment}"
    else:
        out = f"\tor.b\t{p},d0{comment}"
    return out

def f_and(args,comment):
    p = args[0]
    out = None
    if p == "d0":
        out = f"\ttst.b\td0{comment}"
    elif is_immediate_value(p):
        out = f"\tand.b\t#{p},d0{comment}"
    else:
        out = f"\tand.b\t{p},d0{comment}"

    return out

def f_adc(args,comment):
    if len(args)==1:
        # assume A
        dest = registers["a"]
        source = args[0]
    else:
        dest = args[0]
        source = args[1]
    out = None
    if dest in m68_address_regs:
        # supported but not sure, must be reviewed
        source = addr2data_single.get(source,source)
        out = f"\taddx.w\t{source},{dest}{comment}\n  ^^^^ TODO: review {source} computation above"
        return out

    if source in m68_regs:
        out = f"\taddx.b\t{source},{dest}{comment}"
    elif is_immediate_value(source):
        out = f"\tmove.b\t#{source},d7{comment}\n\taddx.b\td7,{dest}{comment}"
    else:
        out = f"\taddx.b\t{source},{dest}{comment}"
    return out


def f_add(args,comment):
    if len(args)==1:
        # assume A
        dest = registers["a"]
        source = args[0]
    else:
        dest = args[0]
        source = args[1]
    out = None
    if dest in m68_address_regs:
        # supported but not sure, must be reviewed
        source = addr2data_single.get(source,source)
        out = f"\tadd.w\t{source},{dest}{comment}\n  ^^^^ TODO: review {source} computation above"
        return out

    if source in m68_regs:
        out = f"\tadd.b\t{source},{dest}{comment}"
    elif is_immediate_value(source):
        if can_be_quick(source):
            out = f"\taddq.b\t#{source},{dest}{comment}"
        else:
            out = f"\tadd.b\t#{source},{dest}{comment}"
    else:
        out = f"\tadd.b\t{source},{dest}{comment}"
    return out

def f_sbc(args,comment):
    if len(args)==1:
        # assume A
        dest = registers["a"]
        source = args[0]
    else:
        dest = args[0]
        source = args[1]
    out = None
    if dest in m68_address_regs:
        # probably comparison between 2 data registers
        source = addr2data_single.get(source,source)
        dest = addr2data_single.get(dest,dest)
        out = f"\tsub.w\t{source},{dest}{comment}\n     ^^^^ TODO: review compared/subbed registers"

    elif source in m68_regs:
        out = f"\tsubx.b\t{source},{dest}{comment}"
    elif is_immediate_value(source):
        out = f"\tsubx.b\t#{source},{dest}{comment}"
    else:
        out = f"\tsubx.b\t{source},{dest}{comment}"
    return out

def f_sub(args,comment):
    dest = "d0"
    source = args[0]
    out = None
    if source in m68_regs:
        out = f"\tsub.b\t{source},{dest}{comment}"
    elif is_immediate_value(source):
        if can_be_quick(source):
            out = f"\tsubq.b\t#{source},{dest}{comment}"
        else:
            out = f"\tsub.b\t#{source},{dest}{comment}"
    else:
        out = f"\tsub.b\t{source},{dest}{comment}"
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
            out = f"\t{rts_cond_dict[cond]}.b\t{loclab}{out_comment} [...]\n"
        else:
            out = f"\t{rts_cond_dict[cond]}.b\t0f{out_comment} [...]\n"

    out += f"\t{jsr_instruction}\t{func}{comment}"
    if len(args)==2:
        if cli_args.output_mode == "mot":
            out += f"\n{loclab}:"
        else:
            out += f"\n0:"
    if target_address is not None:
        add_entrypoint(parse_hex(target_address))
    return out

def f_cp(args,comment):
    p = args[0]
    out = None
    if p in m68_regs or re.match("\(a\d\)",p) or "," in p:
        out = f"\tcmp.b\t{p},d0{comment}"
    elif p.startswith(out_hex_sign) or p.isdigit():
        if parse_hex(p)==0:
            out = f"\ttst.b\td0{comment}"
        else:
            out = f"\tcmp.b\t#{p},d0{comment}"

    return out

def f_dec(args,comment):
    p = args[0]
    # increment relevant address register instead of low data register
    # ex: INC L => addq.w #1,a0 instead of addq.b #1,d6
    pn = data2addr_lsb.get(p)
    if pn:
        p = pn

    size = "w" if p[0]=="a" else "b"
    out = f"\tsubq.{size}\t#1,{p}{comment}"
    if pn:
        out += f"\n            ^^^^ TODO check dec register {args[0]} or {p}"
    return out

def f_inc(args,comment):
    p = args[0]
    # increment relevant address register instead of low data register
    # ex: INC L => addq.w #1,a0 instead of addq.b #1,d6
    pn = data2addr_lsb.get(p)
    if pn:
        p = pn

    size = "w" if p[0]=="a" else "b"
    out = f"\taddq.{size}\t#1,{p}{comment}"
    if pn:
        out += f"\n            ^^^^ TODO check inc register {args[0]} or {p}"
    return out

def f_ld(args,comment):
    dest,source = args[0],args[1]
    out = None
    direct = False
    word_split = False

    half_msb =  source.startswith(">")
    if half_msb:
        source = source[1:]
        # half-address: must load address register
        # then add relevant data register
        addr_reg = data2addr_msb.get(dest)
        if addr_reg:
            dest = addr_reg
        lsb_data_reg = addr2data_lsb.get(addr_reg)

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
            if not cli_args.use_bc_as_pointer:
                zreg = inv_registers.get(dest)
                if zreg == "bc":
                    direct = False
                    word_split = True

            if direct:
                source = address_to_label_out(source)
                out = f"\tmove.w\t{source}(pc),{dest}{comment}"
            else:
                source_val = None
                try:
                    source_val = parse_hex(source)
                except ValueError:
                    pass

                if not word_split and (source_val is None or source_val > 0x80):  # heuristic limit: address 0x80
                    source = address_to_label_out(source)


                    out = f"\tlea\t{source}(pc),{dest}{comment}"
                    if half_msb:
                        out += f"\n\tand.w\t#{out_hex_sign}FF,{lsb_data_reg}\n\tadd.w\t{lsb_data_reg},{dest}\n\t      ^^^^ TODO: review XX value"
                else:
                    if word_split:
                        dest = addr2data[dest].split("/")
                        if source_val is not None:
                            out = f"\tmove.b\t#{out_hex_sign}{source_val >> 8:02x},{dest[0]}{comment} {source_val}"
                            out += f"\n\tmove.b\t#{out_hex_sign}{source_val & 0xFF:02x},{dest[1]}{comment} {source_val}"
                        else:
                            out = f"\tmove.b\t#{source}_msb,{dest[0]}{comment} {source_val}"
                            out += f"\n\tmove.b\t#{source}_lsb,{dest[1]}{comment} {source_val}"
                    else:
                        # maybe not lea but 16 bit immediate value load
                        dest = addr2data_single.get(dest,dest)
                        out = f"\tmove.w\t#{source},{dest}{comment} {source_val}"
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
        if is_immediate_value(source):
            prefix = "#"
        src = f"{prefix}{source}".lstrip("0")
        if prefix == "#" and parse_hex(source) == 0:
            out = f"\tclr.b\t{dest}{comment}"
        else:
            out = f"\tmove.b\t{prefix}{source},{dest}{comment}"


    return out

f_jr = f_jp

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
            # single instruction either towards a or without argument
            inst = inst.lower()
            ai = a_instructions.get(inst)
            if ai:
                out = f"\t{ai}d0{comment}"
            else:
                if inst in special_loop_instructions:
                    special_loop_instructions_met.add(inst)  # note down that it's used
                    out = f"\t{jsr_instruction}\t{inst}{comment}\n     ^^^^ TODO: review special instruction inputs"
                else:
                    si = single_instructions.get(inst)
                    if si:
                        out = f"\t{si}{comment}"

        elif itoks:
            inst = itoks[0]
            args = itoks[1:]
            sole_arg = args[0].replace(" ","")
            # pre-process instruction to remove spaces
            # (only required when source is manually reworked, not in MAME dumps)
            #sole_arg = re.sub("(\(.*?\))",lambda m:m.group(1).replace(" ",""),sole_arg)

            # also manual rework for 0x03(ix) => (ix+0x03)
            sole_arg = re.sub("(-?0x[A-F0-9]+)\((\w+)\)",r"(\2+\1)",sole_arg)

            inst = inst.lower()

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
                jargs = [x.strip("#") for x in jargs]
                try:
                    out = conv_func(jargs,comment)
                except Exception as e:
                    print(f"Problem parsing: {l}, args={jargs} ({e})")
                    raise
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
prev_fp = None
for i,line in enumerate(nout_lines):
    line = line.rstrip()
    toks = line.split("|",maxsplit=1)
    if len(toks)==2:
        fp = toks[0].rstrip().split()
        finst = fp[0]
        if finst.startswith(("j","b")) and not finst[1:].startswith(("set","clr","tst","sr","bsr","ra")):
            # conditional branch, examine previous instruction
            if prev_fp and prev_fp[0].startswith(("move.","clr.")):
                nout_lines[i] += f"      ^^^^^^ TODO: review cpu flags ({prev_fp[0]},{finst})\n"
        elif finst == "tst.b" and fp[1] == "d0":
            if prev_fp[-1].endswith(",d0") and not prev_fp[0].startswith("movem"):
                # previous instruction targets d0 but not movem, so no need to test it
                nout_lines[i] = nout_lines[i].replace("tst.b\td0","")
        elif finst.startswith(("rox","addx","subx")):
            # if previous instruction sets X flag properly, don't bother, but rol/ror do not!!
            if prev_fp:
                if prev_fp == ["tst.b","d0"]:
                    # clear carry
                    nout_lines[i] = f"\tCLEAR_XC_FLAGS\t{out_comment} clear carry is not enough\n"+nout_lines[i]
                elif prev_fp[0].startswith("cmp"):
                    nout_lines[i] += "      ^^^^^^ TODO: review cpu X flag, cmp doesn't affect it!\n"
                elif not prev_fp[0].startswith(("rox","add","sub","as","ls")):
                    nout_lines[i] += "      ^^^^^^ TODO: review cpu X flag\n"

        if len(fp)>1:
            args = fp[1].split(",")
            if len(args)==2:
                if args[1].startswith("0x"):
                    nout_lines[i] += "          ^^^^^^ TODO: review absolute 16-bit address write\n"
                elif args[0].startswith("0x"):
                    nout_lines[i] += "       ^^^^^^ TODO: review absolute 16-bit address read\n"
                elif ".w" in finst and "move" in finst and args[1].startswith("a"):
                    nout_lines[i] += "                  ^^^^^^ TODO: review move.w into address register\n"
                elif ".w" in finst and args[0].startswith("a") and args[0][1].isdigit():
                    nout_lines[i] += "                  ^^^^^^ TODO: review move.w from address register\n"

        prev_fp = fp
# post-processing

if cli_args.spaces:
    nout_lines = [tab2space(n) for n in nout_lines]

with open(cli_args.output_file,"w") as f:
    if cli_args.output_mode == "mit":
        f.write("""\t.macro CLEAR_XC_FLAGS
\tmove.w\td7,-(a7)
\tmoveq\t#0,d7
\troxl.b\t#1,d7
\tmovem.w\t(a7)+,d7
\t.endm

\t.macro SET_XC_FLAGS
\tmove.w\td7,-(a7)
\tst\td7
\troxl.b\t#1,d7
\tmovem.w\t(a7)+,d7
\t.endm

\t.macro\tINVERT_XC_FLAGS
\tjcs\t0f
\tSET_XC_FLAGS
\tbra.b\t1f
0:
\tCLEAR_XC_FLAGS
1:
\t.endm

\t.macro\tSET_X_FROM_C
\tjcc\t0f
\tSET_XC_FLAGS
\tbra.b\t1f
0:
\tCLEAR_XC_FLAGS
1:
\t.endm
\t.macro\tSET_C_FROM_X
\tmove.w\td7,-(a7)
\troxl.b\t#1,d7
\troxr.b\t#1,d7
\tmovem.w\t(a7)+,d7
\t.endm

""")
    else:
        f.write("""\tCLEAR_XC_FLAGS:MACRO
\tmoveq\t#0,d7
\troxl.b\t#1,d7
\tENDM
\tSET_XC_FLAGS:MACRO
\tst.b\td7
\troxl.b\t#1,d7
\tENDM
\tINVERT_XC_FLAGS:MACRO
\tbcc.b\tinv0\@
\tSET_XC_FLAGS
\tbra.b\tinv1\@
inv0\@:
\tCLEAR_XC_FLAGS
inv1\@:
\tENDM
""")
    f.writelines(nout_lines)

    if "rld" in special_loop_instructions_met:
        f.write(f"""
{out_start_line_comment} < A0 (HL)
{out_start_line_comment} < D0 (A)
rld:
    movem.w    d1/d2,-(a7)
    move.b    d0,d1        {out_comment} backup A
    clr.w    d2            {out_comment} make sure high bits of D2 are clear
    move.b    (a0),d2       {out_comment} read (HL)
    and.b #0xF,d1        {out_comment} keep 4 lower bits of A
    lsl.w    #4,d2       {out_comment} make room for 4 lower bits
    or.b    d1,d2        {out_comment} insert bits
    move.b    d2,(a0)        {out_comment} update (HL)
    lsr.w    #8,d2        {out_comment} get 4 shifted bits of (HL)
    and.b    #0xF0,d0    {out_comment} keep only the 4 highest bits of A
    or.b    d2,d0        {out_comment} insert high bits from (HL) into first bits of A
    movem.w    (a7)+,d1/d2
    rts

""")
    if "ldd" in special_loop_instructions_met:
        f.write(f"""
{out_start_line_comment} < A0: source (HL)
{out_start_line_comment} < A1: destination (DE)
{out_start_line_comment} < D1: decremented (16 bit)
ldd:
    move.b    (a0),(a1)
    subq.w  #1,a0
    subq.w  #1,a1
    subq.w    #1,d1
    rts
""")
    if "lddr" in special_loop_instructions_met:
        f.write(f"""
{out_start_line_comment} < A0: source (HL)
{out_start_line_comment} < A1: destination (DE)
{out_start_line_comment} < D1: decremented (16 bit)
lddr:
    subq.w    #1,d1
    addq.w  #1,a0
    addq.w  #1,a1
""")
        if cli_args.output_mode == "mit":
            f.write(f"""0:
    move.b    -(a0),-(a1)
    dbf        d1,0b
""")
        else:
            f.write(f""".loop:
    move.b    -(a0),-(a1)
    dbf        d1,.loop
""")
        f.write("""
    subq.w  #1,a0
    subq.w  #1,a1
    clr.w    d1
    rts
""")
    if "ldi" in special_loop_instructions_met:
        f.write(f"""
{out_start_line_comment} < A0: source (HL)
{out_start_line_comment} < A1: destination (DE)
{out_start_line_comment} < D1: decremented (16 bit)
ldi:
    move.b    (a0)+,(a1)+
    subq.w    #1,d1
    rts
""")

    if "ldir" in special_loop_instructions_met:
        f.write(f"""
{out_start_line_comment} < A0: source (HL)
{out_start_line_comment} < A1: destination (DE)
{out_start_line_comment} < D1: length (16 bit)
ldir:
    subq.w    #1,d1
""")
        if cli_args.output_mode == "mit":
            f.write(f"""0:
    move.b    (a0)+,(a1)+
    dbf        d1,0b
    clr.w    d1
    rts
""")
        else:
            f.write(f""".loop:
    move.b    (a0)+,(a1)+
    dbf        d1,.loop
    clr.w    d1
    rts
""")

    if "lddr" in special_loop_instructions_met:
        f.write(f"""
{out_start_line_comment} < A0: source (HL)
{out_start_line_comment} < A1: destination (DE)
{out_start_line_comment} < D1: length (16 bit)
ldir:
    subq.w    #1,d1
""")
        if cli_args.output_mode == "mit":
            f.write(f"""0:
    move.b    (a0),(a1)
    subq.w  #1,a0
    subq.w  #1,a1
    dbf        d1,0b
    clr.w    d1
    rts
""")
        else:
            f.write(f""".loop:
    move.b    (a0),(a1)
    dbf        d1,.loop
    subq.w  #1,a0
    subq.w  #1,a1
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
""")
        if cli_args.output_mode == "mit":
            f.write(f"""0:
    cmp.b    (a0)+,d0
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
    cmp.b    (a0)+,d0
    beq.b    .out
    dbf        d1,.loop
    clr.w    d1
    {out_start_line_comment} not found: unset Z
    cmp.b   #1,d1
.out:
    rts
""")

    if "cpi" in special_loop_instructions_met:
        f.write(f"""
{out_start_line_comment} < A0: source (HL)
{out_start_line_comment} < D1: decremented
{out_start_line_comment} > D0.B value searched for (A)
{out_start_line_comment} > Z flag if found
{out_start_line_comment} careful: d1 overflow not emulated
cpi:
    subq.w    #1,d1
    cmp.b    (a0)+,d0
    rts
""")

    if "cpd" in special_loop_instructions_met:
        f.write(f"""
{out_start_line_comment} < A0: source (HL)
{out_start_line_comment} < D1: decremented
{out_start_line_comment} > D0.B value searched for (A)
{out_start_line_comment} > Z flag if found
{out_start_line_comment} careful: d1 overflow not emulated
cpi:
    subq.w    #1,d1
    subq.w    #1,a0
    cmp.b    (1,a0),d0
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
print("\nPLEASE REVIEW THE CONVERTED CODE CAREFULLY AS IT MAY CONTAIN ERRORS!\n")
print("(some TODO: review lines may have been added, and the code won't build on purpose)")




