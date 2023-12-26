import os,sys,re,glob
import getopt,traceback,codecs,itertools
#import count_usage

# use special comments like ";!" to declare baselib aliases
# ;!-21170(A4)=ExecBase

import fnmatch,shutil

class Template:
    __VERSION_NUMBER = "1.1"
    __MODULE_FILE = __file__
    __PROGRAM_NAME = os.path.basename(__MODULE_FILE)
    __PROGRAM_DIR = os.path.abspath(os.path.dirname(__MODULE_FILE))
    __BASEREG_RE = re.compile("A([0-6]):([0-9A-F]*)",re.I)

    def __init__(self):
        self.__logfile = ""
        # init members with default values
        self.__base_register = None
        self.__input_file = None
        self.__output_file = None
        self.__lvo_dict = {}
        self.__custom_dict = {}
        self.__libname2handle ={}
        self.__libname2libstr ={}
        self.__handle2libname ={}
        self.__entitytype = {}
        self.__lab2line = {}
        self.__line2lab = {}
        self.__offset2line = {}
        self.__line2offset = {}
        self.__base_aliases = {}
        self.__audio_offsets = {4:"ac_len",6:"ac_per",8:"ac_vol",10:"ac_dat"}

    def init_from_sys_args(self,debug_mode = True):
        """ standalone mode """

        self.__do_init()


    @staticmethod
    def __parse_int(v):
        if "$" in v:
            return int(v.replace("$",""),16)
        else:
            return int(v)

    def __do_init(self):
        self.__opts = None
        self.__args = None
        #count_usage.count_usage(self.__PROGRAM_NAME,1)
        self.__parse_args()
        self.__doit()

    def __purge_log(self):
        if self.__logfile:
            try:
                os.remove(self.__logfile)
            except:
                pass

    def __message(self,msg):
        msg = self.__PROGRAM_NAME+(": %s" % msg)+os.linesep
        sys.stderr.write(msg)
        if self.__logfile:
            f = open(self.__logfile,"a")
            f.write(msg)
            f.close()

    def __error(self,msg):
        raise Exception("Error: "+msg)

    def __warn(self,msg):
        self.__message("Warning: "+msg)

    def __load_custom_file(self):
        custom_file = os.path.join(self.__PROGRAM_DIR,"custom.i")
        if os.path.exists(custom_file):
            pass
        else:
            self.__error("Installation error: cannot find %s" % custom_file)
        with open(custom_file) as f:
            for line in f:
                toks = line.split()
                if len(toks)>2 and toks[1].lower()=="equ":
                    self.__custom_dict[self.__parse_int(toks[2])] = toks[0]

    def __load_lvo_file(self):
        lvo_file = os.path.join(self.__PROGRAM_DIR,"LVOs.i")
        if os.path.exists(lvo_file):
            pass
        else:
            self.__error("Installation error: cannot find %s" % lvo_file)

        # load LVOs library

        with open(lvo_file) as f:
            current_key = None
            lvo_line = re.compile(r"\*+\sLVOs for (.*)\.(library|resource)")
            for line in f:
                m = lvo_line.match(line)
                if m:
                    current_key = m.group(1)
                    self.__entitytype[current_key] = m.group(2)
                else:
                    toks = line.split()
                    if len(toks)>2 and toks[1].lower()=="equ":
                        self.__lvo_dict[(current_key,self.__parse_int(toks[2]))] = toks[0]

        self.__libname2handle = {k:k.title()+"Base" for k,_ in self.__lvo_dict}
        self.__libname2libstr = {k:k.title()+"Name" for k,_ in self.__lvo_dict}
        self.__handle2libname = {v:k for k,v in self.__libname2handle.items()}
        # special case for exec short accessing mode
        self.__handle2libname["ExecBase.W"] = "exec"

    def __parse_args(self):
         # Command definition
         # Prepare short & long args from list to avoid duplicate info

        self.__opt_string = ""

        longopts_eq = ["version","help","input-file=","output-file=","base-register="]

        self.__shortopts = []
        self.__longopts = []
        sostr = ""

        for o in longopts_eq:
            i = o[0]

            has_args = o.endswith("=")

            if has_args:
                i += ":"
                o = o[:-1]

            sostr += i
            self.__opt_string += " -"+o[0]+"|--"+o
            if has_args:
                self.__opt_string +=" <>"


            self.__shortopts.append(i)
            self.__longopts.append(o)  # without "equal"

        self.__opts, self.__args = getopt.getopt(sys.argv[1:], sostr,longopts_eq)


        # Command options
        for option, value in self.__opts:
            oi = 0
            if option in ('-v','--'+self.__longopts[oi]):
                print(self.__PROGRAM_NAME + " v" + self.__VERSION_NUMBER)
                sys.exit(0)
            oi += 1
            if option in ('-h','--'+self.__longopts[oi]):
                self.__usage()
                sys.exit(0)
            oi += 1
            if option in ('-i','--'+self.__longopts[oi]):
                self.__input_file = value
            oi += 1
            if option in ('-o','--'+self.__longopts[oi]):
                self.__output_file = value
            oi += 1
            if option in ('-b','--'+self.__longopts[oi]):
                self.__base_register = value

        if self.__input_file == None:
            self.__error("output file not set")

    def __usage(self):

        sys.stderr.write("Usage: "+self.__PROGRAM_NAME+self.__opt_string+os.linesep)

    __EXECCOPY_RE = re.compile("MOVE.*ABSEXECBASE.*,(LAB_....)\s",flags=re.I)
    __LAB_RE = re.compile("(LAB_....|lb_[0-9A-F]+|ABSEXECBASE)",flags=re.I)
    __LABELDECL_RE = re.compile("^(\w+):",flags=re.I)
    __LEAHARDBASE_RE = re.compile("LEA\s+HARDBASE,A([0-6])",flags=re.I)
    __MOVEHARDBASE_RE = re.compile("MOVEA?.L\s+#\$00DFF000,A([0-6])",flags=re.I)
    __SET_AX_RE = re.compile("MOVEA?\.L\s+([\S]+),A([0-6])\s",flags=re.I)
    __SUBROUTINE_RE = re.compile("\s+(JMP|JSR|BSR.*)\s+(\w+)",flags=re.I)
    __SYSCALL_RE = re.compile("(JMP|JSR)\s+(-\d+)\(A6\)",flags=re.I)
    __SYSCALL_RE2 = re.compile("(JMP|JSR)\s+\((-\d+),A6\)",flags=re.I)
    __SYSCALL_RE3 = re.compile("(JMP|JSR)\s+(-\$[\dA-F]+)\(A6\)",flags=re.I)
    __VALID_BASE = re.compile("([\-\w]{3,}(\(A\d\))?)",flags=re.I)
    __VALID_BASE_020 = re.compile("\(([\-\w]{3,},A\d\))",flags=re.I)
    __ADDRESS_REG_RE = re.compile("A([0-6])",flags=re.I)
    __DCL_RE = re.compile("\s+DC\.L\s+(\w+)",flags=re.I)
    __RETURN_RE = re.compile(r"\b(RT[SED])\b",flags=re.I)
    __AX_DI_RE = re.compile("([\s,])(\$[0-9A-F]+|\d+)\(A([0-6])\)",flags=re.I)
    __AX_DI_RE_2 = re.compile("([\s,])\((\$[0-9A-F]+|\d+),A([0-6])\)",flags=re.I)
    __HEXDATA_RE = re.compile("(?:.*;.*:\s+|DC.[WLB]\s+\$)([A-F\d]+)",flags=re.I)

    def __name_execbase_copies_id_labels(self):
        execbase_copies = {"ABSEXECBASE","ABSEXECBASE.W"}
        for i,line in enumerate(self.__input_lines):
            m = self.__EXECCOPY_RE.search(line)
            if m:
                execbase_copies.add(m.group(1))
            else:
                m = self.__LABELDECL_RE.match(line)
                if m:
                    v = m.group(1)
                    self.__lab2line[v] = i
                    self.__line2lab[i] = v

        self.__input_lines = [self.__LAB_RE.sub(lambda m : "ExecBase"
        if m.group(1) in execbase_copies else m.group(1),line) for line in self.__input_lines]

    def __load_known_libs(self):
        for line in self.__input_lines:
            if line.startswith(";!"):
                k,v = line[2:].strip().split("=")
                self.__base_aliases[k]=v
            else:
                break
        for k,v in self.__base_aliases.items():
            print("Alias: {} = {}".format(k,v))

    def __identify_libs(self,debug=False):
        current_libbase = [None]*7

        for i,line in enumerate(self.__input_lines):
            line = line.replace(" (UNKNOWN)","")

            if self.__RETURN_RE.search(line):
                if debug:
                    print("libbase reset due to RTx instruction")
                current_libbase = [None]*7
                continue

            m = self.__SET_AX_RE.search(line)
            if m:
                target_reg = int(m.group(2))
                first_op = m.group(1).replace("(PC)","").replace(",PC)","")
                if first_op.count("(")!=first_op.count(")"):
                    first_op = first_op.strip("(")
                if self.__VALID_BASE.match(first_op) or self.__VALID_BASE_020.match(first_op):
                    # if finds an alias for a lib base, replaces it
                    first_op = self.__base_aliases.get(first_op,first_op)

                    current_libbase[target_reg] = first_op
                    if debug:
                        print("current_libbase for register A{}: {}".format(target_reg,current_libbase[target_reg]))
                else:
                    m = self.__ADDRESS_REG_RE.match(first_op)
                    if m:
                        # source is register
                        source_reg = int(m.group(1))
                        if debug and current_libbase[source_reg]:
                            print("current_libbase for register A{} from A{} ({})".format(target_reg,source_reg,current_libbase[source_reg]))
                        current_libbase[target_reg] = current_libbase[source_reg]
                    else:
                        current_libbase[target_reg] = None

            # handle 68000 or 68020 notation
            m = self.__SYSCALL_RE.search(line) or self.__SYSCALL_RE2.search(line) or self.__SYSCALL_RE3.search(line)
            if m:
                libname = self.__handle2libname.get(current_libbase[6])
                if libname:
                    offset = self.__parse_int(m.group(2))
                    key = (libname,offset)
                    call_name = self.__lvo_dict.get(key)
                    if call_name:
                        self.__input_lines[i] = "\t{}\t({},A6)\t;{} {}.{} (off={})\n".format(m.group(1),
                        call_name,line.partition(";")[2].rstrip(),libname,self.__entitytype[libname],offset)
                else:
                    line = line.rstrip()
                    if ";" not in line:
                        line += "\t;"
                    self.__input_lines[i] = line + " (UNKNOWN)\n"

    __MOVE_LIBHANDLE_RE = re.compile("MOVE\.L\t(.*Base)(?:\(PC\))?,(LAB_[\w\+]+)")

    def __identify_libhandle_copies(self):
        # some programs copy bases in other variables.
        # ex: move.l   IntuitionBase,LAB_0235+2
        # get the destination and rename it
        label_libname = dict()

        for line in self.__input_lines:
            m = self.__MOVE_LIBHANDLE_RE.search(line)
            if m:
                label_libname[m.group(2)] = m.group(1)

        for i,line in enumerate(self.__input_lines):
            newline = re.sub("(LAB_....\+?\d*)",lambda m : label_libname.get(m.group(1),m.group(1)),line)
            if newline != line:
                self.__input_lines[i] = newline


    def __find_os_wrapper_functions(self):
        # some programs (C-based) use wrapper functions to call OS
        # functions, making reverse engineering tedious: name them properly
        repdict = dict()

        entries = set()
        for line in self.__input_lines:
            m = self.__SUBROUTINE_RE.match(line)
            if m:
                entries.add(m.group(2))
            else:
                m = self.__DCL_RE.match(line)
                if m:
                    entries.add(m.group(1))

        previous_line = ""
        entry_found = False
        entry = ""

        for line in self.__input_lines:
            label_line = line.startswith(("SECSTRT","LAB_","lb_"))

            if entry_found:
                # now scanning the current routine
                if label_line:
                    # too complex, bail out
                    entry_found = False
                else:
                    # looking for LVOas JMP
                    m = re.search("JMP.*LVO(\w+).*\s(\w+)\.library",line,flags=re.I)
                    if m:
                        # found an indirection to OS lib
                        lvo = m.group(1)
                        lib = m.group(2)
                        repdict[entry] = "{}_{}".format(lib,lvo)
                        # done
                        entry_found = False

                    elif "MOVE" not in line.upper():
                        # complex instruction: bail out
                        entry_found = False

            else:
                if label_line:
                    # label found. Is this likely to be a label that is called?
                    entry = line.strip("\n:")
                    if entry in entries:
                        entry_found = True


            previous_line = line

        self.__replace_words(repdict)

    def __replace_words(self,repdict):
        for i,line in enumerate(self.__input_lines):
            newline = re.sub(r"\b(\w+)\b",lambda m : repdict.get(m.group(1),m.group(1)),line)
            if newline != line:
                self.__input_lines[i] = newline



    def __get_hex_data(self,line):
        m = self.__HEXDATA_RE.search(line)
        if m:
            return codecs.decode(m.group(1),"hex")
        else:
            return b''

    def __locate_library_names(self):
        label_libname = dict()
        for i,line in enumerate(self.__input_lines):
            if "OpenLibrary,A6" in line or "OpenResource,A6" in line or "FindName,A6" in line:
                # rewind file for a few instructions to try to find a value assigned in A1
                for j in range(i-1,max(i-10,0),-1):
                    if ",A1" in self.__input_lines[j]:
                        libname_load_line = self.__input_lines[j]
                        m = re.search("(LAB_....)([^()]*)(?:\(PC\))?,A1",libname_load_line,flags=re.I)
                        if not m:
                            m = re.search("\((LAB_....([^()]*)),PC\),A1",libname_load_line,flags=re.I)
                        if m:
                            library_name = None
                            label = m.group(1)
                            offset = self.__parse_int(m.group(2)) if m.group(2) else 0
                            labline = self.__lab2line.get(label)
                            if labline is not None:
                                b = b''
                                offset_removed = not bool(offset) # 0 consider offset removed
                                # 20 lines should be enough to contain the whole hex data
                                for k in range(labline,labline+20):
                                    hexline = self.__input_lines[k].strip()
                                    b += self.__get_hex_data(hexline)
                                    if not offset_removed and len(b)>=offset:
                                        # remove offset
                                        b = b[offset:]
                                        offset_removed = True
                                    if 0 in b:  # nul termination detected
                                        try:
                                            library_name = b[:b.index(0)].decode()
                                            # add offset or we cannot replace it properly
                                            label += m.group(2)
                                            library_name_no_suffix = library_name.split(".")[0]
                                            label_libname[label] = self.__libname2libstr.get(library_name_no_suffix,library_name_no_suffix.title()+"Name")
                                            break
                                        except UnicodeDecodeError:
                                            self.__warn("Cannot decode library name at {}".format(label))
                                else:
                                    # 0 not found: truncated
                                    pass
                                if library_name:
                                    address_regs = [""]*7
                                    self.__message("{} identified as {} string".format(label,library_name))
                                    # now try to locate the write from D0 to libbase line so we can identify libbase
                                    # some wannabe relocatable code could use LEA xxx(pc),Ax then move.l  D0,(Ax)
                                    # we'll try to catch those too
                                    for k in range(i+1,min(i+7,len(self.__input_lines))):
                                        libhandle_write_line = self.__input_lines[k]
                                        # compute current values of address registers if they contain labels
                                        # (naive but allows to catch those LEA + MOVE D0,(Ax) occurrences
                                        m = re.search("(LAB_....[^()]*)(?:\(PC\))?,A(\d)",libhandle_write_line,flags=re.I)
                                        if m:
                                            label_offset = m.group(1)
                                            register_number = int(m.group(2))
                                            address_regs[register_number] = label_offset

                                        if "D0," in libhandle_write_line:
                                            library_handle_label = None
                                            m = re.search("D0,(LAB_....[^\s]*)",libhandle_write_line,flags=re.I)
                                            if m:
                                                library_handle_label = m.group(1)
                                            else:
                                                m = re.search("D0,\(A(\d)\)",libhandle_write_line,flags=re.I)
                                                if m:
                                                    register_number = int(m.group(1))
                                                    library_handle_label = address_regs[register_number]

                                            if library_handle_label:
                                                library_handle_name = self.__libname2handle.get(library_name_no_suffix,library_name_no_suffix.title()+"Base")
                                                label_libname[library_handle_label] = library_handle_name
                                                break
        # now replacing the labels and whatnot be readable alternatives. one pass for labels with possible offset
        for i,line in enumerate(self.__input_lines):
            newline = re.sub("(LAB_....\+?\d*)",lambda m : label_libname.get(m.group(1),m.group(1)),line)
            if newline != line:
                self.__input_lines[i] = newline

    def __custom_offset_replace_1(self,m):
        return self.__custom_offset_replace(m,True)
    def __custom_offset_replace_2(self,m):
        return self.__custom_offset_replace(m,False)

    def __custom_offset_replace(self,m,old_style):
        sep,offset,regnum = m.groups()
        symbolic_offset = None

        if int(regnum) == self.__hardbase:
            offset = self.__parse_int(offset)
            symbolic_offset = self.__custom_dict.get(offset)
            if not symbolic_offset:
                higher_bits = offset>>4
                # check if not audio or bitplane or other stuff not in .i file because
                # needs some offset
                if 0xA <= higher_bits <= 0xD:
                    sub_offset = self.__audio_offsets.get(offset & 0xF)
                    if sub_offset:
                        symbolic_offset = "{}+{}".format(self.__custom_dict.get(offset & 0xF0),sub_offset )
                else:
                    # bitplanes, sprites, colors...
                    for c in [[0xE,0xF],[0x12,0x13],[0x14,0x15,0x16,0x17],[0x18,0x19,0x1A,0x1B]]:
                        if higher_bits in c:
                            base = c[0]<<4
                            symbolic_offset = "{}+{}".format(self.__custom_dict.get(base),offset-base)
                            break



        return ("{}{}(A{})" if old_style else "{}({},A{})").format(sep,symbolic_offset or offset,regnum)

    def __identify_custom_registers(self):
        self.__hardbase = None

        for i,line in enumerate(self.__input_lines):
            if self.__hardbase:
                pass
            m = self.__LEAHARDBASE_RE.search(line) or self.__MOVEHARDBASE_RE.search(line)
            if m:
                self.__hardbase = int(m.group(1))
            else:
                m = self.__RETURN_RE.search(line)
                # reset on RTE/RTS
                if m:
                    self.__hardbase = None
                else:
                    # we use 2 different replace methods, because we don't want to change the asm
                    # "style" (68000: 12(A0), 68020+ (12,A0)) for all lines, creates too many diffs
                    newline = self.__AX_DI_RE.sub(self.__custom_offset_replace_1,line)
                    newline = self.__AX_DI_RE_2.sub(self.__custom_offset_replace_2,newline)
                    if newline != line:
                        self.__input_lines[i] = newline

    def __create_offset2line_dict(self):
        # create offset => line dict

        offset_re = re.compile(";([0-9A-F]+)",re.I)
        for i,line in enumerate(self.__input_lines):
            m = offset_re.search(line)
            if m:
                co = int(m.group(1),16)
                self.__offset2line[co] = i
                self.__line2offset[i] = co

    def __pack_jump_tables(self):
        previous_is_jmp = False
        new_lines = []
        # 4EF9 + label in a data section means that someone has put
        # a jump table in the data section...
        dc_jmp_re = re.compile("\s+dc.w\s+\$4EF9\s+;([0-9A-F]+)",re.I)
        dc_lab_re = re.compile("\s+dc.l\s+(\S+)",re.I)
        previous_line = ""
        for line in self.__input_lines:
            if previous_is_jmp:
                previous_is_jmp = False
                m = dc_lab_re.match(line)
                if not m:
                    # ooops... abort abort
                    new_lines.append(previous_line)
                else:
                    line = "\tJMP\t{}\t;{}\n".format(m.group(1),jmp_offset)
            else:
                m = dc_jmp_re.match(line)
                if m:
                    jmp_offset = m.group(1)
                    previous_is_jmp = True
                    previous_line = line  # store previous line just in case...
                    continue        # do not write that line

            new_lines.append(line)

        self.__input_lines = new_lines

    def __link_offset_references_to_labels(self):

        # if base register is set, try to locate its init address
        # then comment call references with the actual offset in the file
        if self.__base_register is not None:
            register_index,register_set_offset = self.__register_index,self.__register_set_offset
            self.__create_offset2line_dict()

            if register_set_offset:
                register_set_offset = int(register_set_offset,16)
                # grab the line with the offset
                lineno = self.__offset2line.get(register_set_offset)
                if lineno is not None:
                    register_set_line = self.__input_lines[lineno]
                else:
                    self.__error("Offset {:x} not found in file".format(register_set_offset))
            else:
                # automatic mode TODO
                self.__error("Automatic mode not implemented yet")

            regset_re = re.compile("\s+lea\s+(.*),a{}".format(register_index),re.I)
            m = regset_re.match(register_set_line)
            if not m:
                self.__error("Line at offset {:x} doesn't match register load: {}".format(register_set_offset,register_set_line.strip()))
            expression = m.group(1)
            # try to match several expressions to compute data
            for ere in ["(\w+)\(pc\)","\((\w+),pc\)","(\w+)\+(\d+)"]:
                m = re.match(ere,expression,flags=re.I)
                if m:
                    label = m.group(1)
                    line = self.__lab2line[label]
                    label_base_offset = self.__line2offset.get(line+1)
                    if label_base_offset is None:
                        self.__error("Cannot find offset of base label {}".format(label))
                    if len(m.groups())==2:
                        # add offset
                        label_base_offset += int(m.group(2))
                    break
            # we have base offset for the label
            self.__message("Base offset for A{} is ${:x}".format(register_index,label_base_offset))

            ere = re.compile("\(-(\d+),A{0}\)|-(\d+)\(A{0}\)".format(register_index),re.I)
            jmp_re = re.compile("\tJMP\t(\w+)",re.I)

            # now scan the file & comment when offset is found
            for i,line in enumerate(self.__input_lines):
                if " (links:" not in line:
                    toks = ere.findall(line)
                    if toks:
                        toks = [int(x) for x in itertools.chain.from_iterable(toks) if x]
                        outtoks = []
                        for offset in toks:
                            code_offset = label_base_offset-offset
                            lineno = self.__offset2line.get(code_offset)
                            if lineno is not None:
                                # try to see if it matches a label (line above)
                                label_above = self.__line2lab.get(lineno-1)
                                if label_above:
                                    outtoks.append("aka={}".format(label_above))
                                else:
                                    # last chance: if there's a JMP line here, link it
                                    link_line = self.__input_lines[lineno]
                                    m = jmp_re.match(link_line)
                                    if m:
                                        outtoks.append("jmp={}".format(m.group(1)))
                                    else:
                                        lineno = None
                            # default case
                            if lineno is None:
                                outtoks.append("off=${:x}".format(code_offset))

                        # append the tokens as a comment
                        newline = "{} (links:{})\n".format(self.__input_lines[i].rstrip(),",".join(outtoks))
                        self.__input_lines[i] = newline

    def __doit(self):
        # if base register is set, try to locate its init address
        # then comment call references with the actual offset in the file
        if self.__base_register is not None:
            m = self.__BASEREG_RE.match(self.__base_register)
            if not m:
                self.__error("base register expression must be A<regindex>:<offset_in_hex>\n"
                "or A<regindex>:<empty> for autoscan. Ex: A6:456A2 or A4:")
            self.__register_index,self.__register_set_offset = m.groups()

        if self.__input_file == self.__output_file:
            self.__output_file = None  # overwrite, don't trust exe!

        if self.__output_file == None:
            output_file = self.__input_file+".temp"
        else:
            output_file = self.__output_file

        self.__load_lvo_file()
        self.__load_custom_file()

        # reading the full file lines
        with open(self.__input_file) as f:
            self.__input_lines = f.readlines()

        # read special comments at start
        self.__load_known_libs()

        # some jump tables are in data sections.
#    DC.W    $4ef9            ;00314
#    DC.L    lb_00000        ;00316: 00000000
#
# convert to: JMP lb_00000

        self.__pack_jump_tables()

        # try to see if execbase is copied in a local label or something
        # also build a label => line dict for faster label lookup
        self.__name_execbase_copies_id_labels()

        # first pass to identify exec calls
        self.__identify_libs(debug=False)

        # now locate the library names if possible, around the "OpenLibrary" calls
        self.__locate_library_names()

        # now identify other lib calls
        self.__identify_libs()

        self.__identify_libhandle_copies()

        # now try to find relay functions and rename them
        self.__find_os_wrapper_functions()

        # now try to replace $DFF000-based stuff
        self.__identify_custom_registers()

        # now try to link base offsetted addresses to real symbols
        self.__link_offset_references_to_labels()


        #sys.stdout.write("".join(self.__input_lines))
        with open(output_file,"w") as f:
            f.writelines(self.__input_lines)

        if self.__output_file == None:
            self.__message("Updating input file %s" % self.__input_file)
            shutil.move(output_file,self.__input_file)

if __name__ == '__main__':
    """
        Description :
            Main application body
    """


    o = Template()
    o.init_from_sys_args(debug_mode = True)
    #o.init("output_file")
