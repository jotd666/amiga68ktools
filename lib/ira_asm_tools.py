import re,os,subprocess,shutil


general_instruction_re = re.compile(r"^\s+\b([^\s]*)\b\s*([^\s]*)\s*;([a-f0-9]{2,}): (.*)")
dc_instruction_re = re.compile(r"^\s+\b(DC\..)\b\s*([^\s]*)\s*;([a-f0-9]{2,})")
decl_label_re = re.compile("^(\w+):")

def repl_function(m):
    s = m.group(1)
    # prepends LAB_ to every special label so check for a label in a string is easy
    # lame but efficient, I'm not writing an assembler in python (that will be my next project :))
    if s.startswith(("SECSTRT_","INIT")) or s in ["ROMTAG","IDSTRING","EXECLIBNAME","ENDSKIP"] or "TABLE" in s or "FUNC" in s:
        s = "LAB_"+s
    return s

def get_line_address(l):
    return int(l.split(";")[-1].split(":")[0],16)
def get_line_size(l):
    return len(l.split(";")[-1].split(":")[1].strip())//2

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
            self.lines = [re.sub("(\w+)",repl_function,l) for l in f]

        self.start_address = start_address
        self.binary_contents = None
        if binary_filepath:
            with open(binary_filepath,"rb") as f:
                self.binary_contents = f.read()

        self.filepath = asm_filepath
        self.binpath = binary_filepath
        self.label_addresses = {}
        self.line_addresses = {}

        for i,l in enumerate(self.lines):
            try:
                try:
                    address = get_line_address(l)
                    self.line_addresses[i] = address
                except ValueError:
                    pass

                m = decl_label_re.match(l)
                if m:
                    label = m.group(1)
                    if ";" in l:
                        address = get_line_address(l)
                    else:
                        nextl = self.lines[i+1]
                        try:
                            address = get_line_address(nextl)
                            self.label_addresses[label] = address
                            self.line_addresses[i] = address
                        except ValueError:
                            print("warning: address of label {} can't be computed".format(label))

            except Exception as e:
                print("exception line {}: {}".format(i,l))
                raise (e)

        self.address_labels = {v:k for k,v in self.label_addresses.items()}
        self.address_lines = {v:k for k,v in self.line_addresses.items()}
