import re,os,subprocess,shutil


general_instruction_re = re.compile(r"^\s+\b([^\s]*)\b\s*([^\s]*)\s*;([a-f0-9]{2,}): (\w{2,})",flags=re.I)
dc_instruction_re = re.compile(r"^\s+\b(DC\..)\b\s*([^\s]*|[\"'].*[\"'])\s*;([a-f0-9]{2,})",flags=re.I)
decl_label_re = re.compile("^(\w+):")
ext_re_values_re = re.compile(r"\b(EXT_\w+)\s*(=|EQU)\s*\$(\w+)")

class AsmException(Exception):
    pass

def split_params(params):
    """ split params taking account of parentheses
    I'm sick of how many times I have coded this, I copied it
    from my 6502268k.py converter, now it's here too
    """
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

def get_offset(line):
    """ try to extract offset from either offset comment or label
    """
    offset = None
    size = 0
    m = general_instruction_re.match(line)
    if m:
        offset = m.group(3)
        size = len(m.group(4))//2
    else:
        m = dc_instruction_re.match(line)
        if m:
            dc = m.group(1)[-1].lower()
            offset = m.group(3)
            size = {"l":4,"w":2,"b":1}[dc]
            args = m.group(2)
            if size == 1 and '"' in args or "'" in args:
                size *= len(args)-2
            else:
                size *= args.count(",")+1
        else:
            m = re.match("lb_(\w+)",line)
            if m:
                offset = m.group(1)

    if offset is None:
        raise AsmException("Cannot compute offset for line: {}".format(line))
    return (int(offset.split("_")[0],16),size)

def convert_instruction_to_data(line):
    m = general_instruction_re.match(line)
    if m:
        offset,comment = m.group(3),m.group(4)
        offset = int(offset,16)
        result = ["\tdc.w\t${}\t;{:05x}\n".format(comment[i:i+4],offset+i//2) for i in range(0,len(comment),4)]
        line = "".join(result)
    return line

def is_branch_instruction(inst):
    """ checks if the instruction is a branch instruction"""
    instws = inst.split(".")[0].lower()
    return instws in ["dbf","jmp","jsr"] or (instws.startswith("b") and len(instws)<4) or \
             (instws.startswith("d") and is_branch_instruction(instws[1:]))

def get_dc_line(hexstring,comment=None):
    """
    returns dc.x line
    """
    table = ["B","W","L","L"]
    idx = len(hexstring)//2 - 1
    line = "\tDC.{}\t${}".format(table[idx],hexstring)
    if comment:
        return "{}\t\t;{}\n".format(line,comment)
    else:
        return line+"\n"


def repl_function(m):
    s = m.group(1)
    # prepends LAB_ to every special label so check for a label in a string is easy
    # lame but efficient, I'm not writing an assembler in python (that will be my next project :))
    if s.startswith(("SECSTRT_","INIT")) or s in ["ROMTAG","IDSTRING","EXECLIBNAME","ENDSKIP"] or "TABLE" in s or "FUNC" in s:
        s = "LAB_"+s
    return s

def parse_instruction_line(line):
    m = general_instruction_re.match(line)
    if m:
        offset = m.group(3)
        size = len(m.group(4))//2
        instruction = re.sub("\s*;.*","",line)
        toks = instruction.split()
        args = []
        if len(toks)>1:
            args = split_params(toks[1])

        return {"address":int(offset,16),"size":size,"instruction":toks[0],"arguments":args}

    m = dc_instruction_re.match(line)
    if m:
        last_char = m.group(1).lower()[-1]
        size = {"b":1,"w":2,"l":4}[last_char]
        address = int(m.group(3),16)
        instruction = m.group(1)
        args = [m.group(2)]

        return {"address":address,"size":size,"instruction":instruction,"arguments":args}



def get_line_address(l):
    # get the ;xxxxx part with or without following colon
    # also accepts manual following comments even without ":"
    toks = l.split(";")[-1].split(":")
    if len(toks)==1:
        toks = toks[0].split()
    if not toks:
        return 0
    return int(toks[0],16)

def get_line_size(l):
    stoks = l.split(";")
    if len(stoks)==2:
        last_tok = stoks[-1]
        ctoks = last_tok.split(":")
        if len(ctoks)==2:
            return len(ctoks[1].strip())//2

    elif stoks:
        ftok = stoks[0].strip()
        if not ftok or ftok.endswith(":"):
            return 0

        ftok = ftok.split()
        mnemonic = ftok[0].lower()
        if mnemonic.startswith("dc."):
            size = {"b":1,"w":2,"l":4}[mnemonic[3]]
            return size * (ftok[1].count(",")+1)
    return 0

class AsmFile:
    def __init__(self,asm_filepath,binary_filepath=None,start_address=None):
        if not os.path.exists(asm_filepath):
            asm_dir = os.path.dirname(asm_filepath)
            if binary_filepath:
                temp_bin = os.path.join(asm_dir,os.path.basename(binary_file))
                if not os.path.exists(temp_bin):
                    shutil.copy(binary_file,asm_dir)
                    delbin = True
                opts = ["ira","-a"]
                if start_address:
                    opts.append("-offset=${:x}".format(start_address))
                subprocess.check_call(opts+[os.path.basename(binary_file)],cwd=asm_dir)
                if delbin:
                    os.remove(temp_bin)
        with open(asm_filepath) as f:
            # first transform special labels that IRA thinks it's smart to use instead of "LAB_"
            # the best way would be to have a "is_a_label" method but that would mean properly parse the asm instruction
            # with nested parentheses and all. The following seems to work properly so why bother, let's pre-process
            self.lines = [re.sub("(\w+)",repl_function,l) if "dc.b" not in l else l for l in f]

        self.start_address = start_address
        self.binary_contents = None
        if binary_filepath:
            with open(binary_filepath,"rb") as f:
                self.binary_contents = f.read()

        self.filepath = asm_filepath
        self.binpath = binary_filepath
        self.label_addresses = {}
        self.line_addresses = {}
        self.ext_addresses = {}

        for i,l in enumerate(self.lines):
            try:
                try:
                    address = get_line_address(l)
                    self.line_addresses[i] = address
                except ValueError:
                    pass

                m = ext_re_values_re.match(l)
                if m:
                    self.ext_addresses[m.group(1)] = int(m.group(3),16)

                m = decl_label_re.match(l)
                if m:
                    label = m.group(1)
                    try:
                        if ";" in l:
                            address = get_line_address(l)
                        else:
                            nextl = self.lines[i+1]
                            address = get_line_address(nextl)
                            self.label_addresses[label] = address
                            self.line_addresses[i] = address
                    except ValueError:
                        if ":MACRO" in l:
                            pass
                        else:
                            print("warning: address of label {} can't be computed".format(label))

            except Exception as e:
                print("exception line {}: {}".format(i,l))
                raise (e)

        self.address_labels = {v:k for k,v in self.label_addresses.items()}
        self.address_lines = {v:k for k,v in self.line_addresses.items()}
