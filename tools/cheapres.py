import os,sys,re,glob
import getopt,traceback,codecs
#import count_usage

import fnmatch,shutil

class Template:
    __VERSION_NUMBER = "1.0"
    __MODULE_FILE = __file__
    __PROGRAM_NAME = os.path.basename(__MODULE_FILE)
    __PROGRAM_DIR = os.path.abspath(os.path.dirname(__MODULE_FILE))

    def __init__(self):
        self.__logfile = ""
        # init members with default values
        self.__input_file = None
        self.__output_file = None
        self.__lvo_dict = {}
        self.__custom_dict = {}
        self.__libname2handle ={}
        self.__libname2libstr ={}
        self.__handle2libname ={}
        self.__entitytype = {}
        self.__lab2line = {}
        self.__audio_offsets = {4:"ac_len",6:"ac_per",8:"ac_vol",10:"ac_dat"}

    def init_from_sys_args(self,debug_mode = True):
        """ standalone mode """

        self.__do_init()

# uncomment if module mode is required
##    def init(self,my_arg_1):
##        """ module mode """
##        # set the object parameters using passed arguments
##        self.__output_file = my_arg_1
##        self.__doit()

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


    def __parse_args(self):
         # Command definition
         # Prepare short & long args from list to avoid duplicate info

        self.__opt_string = ""

        longopts_eq = ["version","help","input-file=","output-file="]

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

        if self.__input_file == None:
            self.__error("output file not set")

    def __usage(self):

        sys.stderr.write("Usage: "+self.__PROGRAM_NAME+self.__opt_string+os.linesep)

    __EXECCOPY_RE = re.compile("MOVE.*ABSEXECBASE.*,(LAB_....)\s",flags=re.I)
    __LAB_RE = re.compile("(LAB_....|ABSEXECBASE)",flags=re.I)
    __LABELDECL_RE = re.compile("(LAB_....):",flags=re.I)
    __LEAHARDBASE_RE = re.compile("LEA\s+HARDBASE,A([0-6])",flags=re.I)
    __MOVEHARDBASE_RE = re.compile("MOVEA?.L\s+#\$00DFF000,A([0-6])",flags=re.I)
    __SET_AX_RE = re.compile("MOVEA?\.L\s+([\S]+),A([0-6])\s",flags=re.I)
    __SYSCALL_RE = re.compile("(JMP|JSR)\s+(-\d+)\(A6\)",flags=re.I)
    __SYSCALL_RE2 = re.compile("(JMP|JSR)\s+\((-\d+),A6\)",flags=re.I)
    __SYSCALL_RE3 = re.compile("(JMP|JSR)\s+(-\$[\dA-F]+)\(A6\)",flags=re.I)
    __VALID_BASE = re.compile("([\-\w]{3,}(\(A\d\))?)",flags=re.I)
    __ADDRESS_REG_RE = re.compile("A([0-6])",flags=re.I)
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
                    self.__lab2line[m.group(1)] = i

        self.__input_lines = [self.__LAB_RE.sub(lambda m : "ExecBase"
        if m.group(1) in execbase_copies else m.group(1),line) for line in self.__input_lines]

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
                first_op = m.group(1).replace("(PC)","").strip("()").replace(",PC","")
                if self.__VALID_BASE.match(first_op):
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

    def __doit(self):

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

        # now try to replace $DFF000-based stuff
        self.__identify_custom_registers()


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
