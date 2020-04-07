#!/usr/bin/python

import os,sys,re
import getopt,traceback
import glob

import asm_parsing

class M68kChecker:
    __VERSION_NUMBER = "1.0"
    __MODULE_FILE = sys.modules[__name__].__file__
    __PROGRAM_NAME = os.path.basename(__MODULE_FILE)
    __PROGRAM_DIR = os.path.abspath(os.path.dirname(__MODULE_FILE))

    __LABEL_WITH_OFFSET_RE = re.compile(r"(.*)\+(\d+)")

    def __init__(self):
        self.__logfile = ""
        # init members with default values
        self.__output_file = ""
        self.__input_files = []
        self.__print_violation_source = True

    def init_from_sys_args(self,debug_mode = True):
        """ standalone mode """

        try:
            self.__do_init()
        except Exception:
            if debug_mode:
                # get full exception traceback
                traceback.print_exc()
            else:
                self.__message(str(sys.exc_info()[1]))

            sys.exit(1)

# uncomment if module mode is required
##    def init(self,my_arg_1):
##        """ module mode """
##        # set the object parameters using passed arguments
##        self.__output_file = my_arg_1
##        self.__doit()

    def __do_init(self):
        self.__opts = None
        self.__args = None
        #count_usage.count_usage(self.__PROGRAM_NAME,1)
        self.__parse_args()
        self.__doit()

    def __purge_log(self):
        if self.__logfile != "":
            try:
                os.remove(self.__logfile)
            except:
                pass

    def __message(self,msg):
        msg = self.__PROGRAM_NAME+(": %s" % msg)+os.linesep
        sys.stderr.write(msg)
        if self.__logfile != "":
            f = open(self.__logfile,"a")
            f.write(msg)
            f.close()

    def __error(self,msg):
        raise Exception("Error: "+msg)

    def __warn(self,msg):
        self.__message("Warning: "+msg)

    def __parse_args(self):
         # Command definition
         # Prepare short & long args from list to avoid duplicate info

        self.__opt_string = ""

        longopts_eq = ["version","help","input-file="]

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
                self.__input_files.extend(glob.glob(value))

        if len(self.__input_files) == 0:
            self.__error("no input files")

    def __usage(self):

        sys.stderr.write("Usage: "+self.__PROGRAM_NAME+self.__opt_string+os.linesep)

    def __report_violation(self,asm_file,message,start_line,end_line=0):
        e = "%s:%d:%s" % (asm_file.filename,start_line+1,message)
        print("VIOLATION:"+e)
        if self.__print_violation_source:
            if end_line == 0:
                end_line = start_line+1
            for i in range(start_line,end_line):
                print(asm_file.get_raw_line(i))

    def __check_visible_self_modifying_code(self,asm_file):
        ial = asm_file.get_instruction_addresses()
        for ia in ial:
            i = asm_file.get_instruction(ia)
            if len(i.operand) == 2:
                last_op = i.operand[1]
                if last_op.write and last_op.addressing_mode == asm_parsing.AddressingMode.DIRECT:
                    # check if this is a label with an offset added to it (move D0,LAB_XXXX+2)
                    target = i.operand[1].token[0]
                    m = self.__LABEL_WITH_OFFSET_RE.match(target)
                    if m:
                        label_without_offset = m.group(1)
                        label_offset = int(m.group(2))
                        if label_without_offset in asm_file.label_address:

                            label_address = asm_file.label_address[label_without_offset]
                            ia2 = asm_file.get_next_instruction_address(label_address)
                            if ia2 != -1:
                                target_instruction = asm_file.get_instruction(ia2)
                                # this can be a false alarm, since most data is disassembled as
                                # fake code

                                if len(target_instruction.operand) > 0: # should always be true
                                    violation = False
                                    if label_offset >= 4 and len(target_instruction.operand) > 1:
                                        # sometimes SMC affects second operand
                                        target_operand_index = 1
                                        target_op = target_instruction.operand[target_operand_index]
                                        if target_op.addressing_mode == asm_parsing.AddressingMode.DIRECT:
                                            # modifies last operand of "move.l d0,$1234"
                                            # not very common
                                            violation = True
                                    else:
                                        target_operand_index = 0
                                        target_op = target_instruction.operand[target_operand_index]
                                        if target_instruction.mnemonic == "dc":
                                            pass
                                        elif target_op.addressing_mode == asm_parsing.AddressingMode.DIRECT:
                                            # ex: JSR addr
                                            violation = True
                                        elif target_op.addressing_mode == asm_parsing.AddressingMode.IMMEDIATE:
                                        # bingo, well we still have to round some common constructions out
                                        # to avoid too many false alarms
                                            if target_instruction.instruction_like(["e?ori"]):
                                                if target_instruction.operand[0].token[0] == 0:
                                                # 0.L translates as "ORI.B #$00,D0": false alarm
                                                    pass
                                            else:
                                                violation = True
                                    if violation:
                                        # avoid violation if next instruction is a data (DC)

                                        next_target_instruction = asm_file.get_next_instruction(ia2)

                                        if next_target_instruction.mnemonic != "dc":
                                            self.__report_violation(asm_file,"self-modifying code",ia)
                                            self.__report_violation(asm_file,"self-modifying code target here",ia2-1,ia2+3)

    def __check_invisible_self_modifying_code(self,asm_file):
        ial = asm_file.get_instruction_addresses()
        for ia in ial:
            i = asm_file.get_instruction(ia)
            if len(i.operand) == 2:
                last_op = i.operand[1]
                if last_op.write and last_op.addressing_mode == asm_parsing.AddressingMode.DIRECT:
                    # check if this is a label with an offset added to it (move D0,LAB_XXXX+2)
                    target = i.operand[1].token[0]
                    if target.find('+') == -1 and target in asm_file.label_address:
                        label_address = asm_file.label_address[target]
                        ia2 = -1
                        for ia2i in ial:
                            if ia2i > label_address:
                                ia2 = ia2i
                                break
                        if ia2 != -1:
                            target_instruction = asm_file.get_instruction(ia2)
                            # this can be a false alarm, since most data is disassembled as
                            # fake code
                            violation = False

                            if target_instruction.mnemonic == "dc":
                                pass
                            elif target_instruction.instruction_like(["e?ori"]) and target_instruction.operand[1].token[0] == "D0":
                                # 0.L translates as "ORI.B #$00,D0": false alarm
                                pass
                            elif target_instruction.instruction_like(["rts","nop","b..$"]):
                                violation = True
                            elif target_instruction.instruction_like(["[alr][os]x?[rl]","or","and"]):
                                # logical instructions with register operands are often tweaked
                                first_op = target_instruction.operand[0]
                                if first_op.addressing_mode == asm_parsing.AddressingMode.REGISTER:
                                    violation = True
                            if violation:
                                self.__report_violation(asm_file,"self-modifying code",ia)
                                self.__report_violation(asm_file,"self-modifying code target here",ia2-1,ia2+3)

    def __check_cpu_dependent_loops(self,asm_file):
        ial = asm_file.get_instruction_addresses()
        for ia in ial:
            i = asm_file.get_instruction(ia)
            if i.is_jump():
                dbf_incdec_reg = None
                # if dbxx instruction, note the register
                if i.instruction_like(["db.+"]):
                    dbf_incdec_reg = i.operand[0].token[0]
                try:
                    last_op = i.operand[-1]
                except:
                    raise Exception("failure line %d, %s" % (ia,str(i)))
                if last_op.addressing_mode == asm_parsing.AddressingMode.DIRECT: # cannot check if not direct
                    jump_label = last_op.token[0]

                    # locate address of label
                    if jump_label in asm_file.label_address:
                        label_address = asm_file.label_address[jump_label]
                        delta = ia - label_address
                        if delta > 0 and delta < 10:  # > 10: big loop, no need to analyse (todo: support comments)
                            # analyze data flow to find edge effects besides sub/add 1 (C-style loops)
                            edge_effect_found = False
                            incdec_reg = dbf_incdec_reg
                            # first pass
                            for lia in range(label_address,ia+1):
                                if asm_file.is_instruction(lia):
                                    li = asm_file.get_instruction(lia)

                                    for o in li.operand:
                                        if o.has_prepost():
                                            edge_effect_found = True
                                            break
                                    if edge_effect_found:
                                        break

                                    if i != li and li.mnemonic == "bra":
                                        # bra within the loop: probably a false alarm
                                        edge_effect_found = True
                                        break
                                    elif li.mnemonic == "lea":
                                        # lea sometimes used to add to address registers
                                        if li.operand:
                                            target_addr_reg = li.operand[1].token[0]
                                            if li.operand[0].uses(target_addr_reg):
                                                # lea 120(a0),a0
                                                edge_effect_found = True
                                                break
                                        else:
                                            print("Issue with LEA")
                                    elif li.instruction_like(["mulu","rts","[al]s[rl]","rox?[lr]","bset","btst","st","move.*","e?or.*","and.*","clr","[bj]sr","pea"]):
                                        # OK, probably not a CPU-dependent loop
                                        # (btst has been added because it may appear in hardware polling loops
                                        # that may otherwise appear as cpu-dependent although they're not)
                                        edge_effect_found = True
                                        break
                                    elif li.instruction_like(["add.*","sub.*"]):
                                        # OK unless first operand is "1" (C-style loop found sometimes, hard to detect by hand)
                                        if li.operand:
                                            first_op = li.operand[0]
                                            if first_op.addressing_mode != asm_parsing.AddressingMode.IMMEDIATE:
                                                # OK, add/sub something complex probably not a CPU-dependent loop
                                                edge_effect_found = True
                                                break
                                            else:
                                                # immediate
                                                ft = first_op.token[0]
                                                if str(ft) == "1":
                                                    second_op = li.operand[1]
                                                    if second_op.addressing_mode == asm_parsing.AddressingMode.REGISTER:
                                                        # note down if register is second operand
                                                        # (avoids a lot of false alarms like sub.l#1,a0 + tst (a0))
                                                        incdec_reg = second_op.token[0]

                                                else:
                                                    edge_effect_found = True
                                                    break
                                    else:
                                        # search for indirect addressing in operands with pre/post ops
                                        for o in li.operand:
                                            if o.prepost_operation != "":
                                                edge_effect_found = True
                                                break

                            if not edge_effect_found and incdec_reg != None:
                                # second pass: try to find an instruction with indirect operands
                                # referencing the decrement register

                                for lia in range(label_address+1,ia+1):
                                    try:

                                        li = asm_file.get_instruction(lia)
                                        for o in li.operand:
                                            if o.addressing_mode == asm_parsing.AddressingMode.INDIRECT:
                                                # scan tokens
                                                if o.uses(incdec_reg):
                                                    edge_effect_found = True

                                    except:
                                        pass
                                    if edge_effect_found:
                                        break

                            if not edge_effect_found:
                                self.__report_violation(asm_file,start_line=label_address,end_line=ia+1,message="probable CPU-dependent/infinite loop for label '%s'" % jump_label)

    def __check_forbidden_stuff(self,asm_file):
        """
        check RESET, move to/from VBR & CACR & move from SR (68000 only)
        """

        ial = asm_file.get_instruction_addresses()
        for ia in ial:
            i = asm_file.get_instruction(ia)
            if i.mnemonic == "reset":
                self.__report_violation(asm_file,start_line=ia,message="instruction '%s' not allowed" % i.mnemonic)
            else:
                # check operands
                if len(i.operand) > 0:
                    fop = i.operand[0]
                    if len(fop.token) > 0:
                        ft = fop.token[0]
                        if str(ft).lower() == "sr":
                                self.__report_violation(asm_file,start_line=ia,message="move from sr is privileged from 68010+")

                    for o in i.operand:
                        for t in o.token:
                            tl = str(t).lower()
                            if ["vbr","cacr"].count(tl) != 0:
                                self.__report_violation(asm_file,start_line=ia,message="operand '%s' not allowed" % tl)

    def __process_file(self,filepath):
        with open(filepath,"rb") as f:
            c1=ord(f.read(1))
            c2=ord(f.read(1))
            c3=ord(f.read(1))
            c4=ord(f.read(1))
        if (c1<<24) + (c2<<16) + (c3<<8) + c4 == 0x3F3:
            # this is an executable: use IRA to disassemble it
            ira_path = os.path.join(self.__PROGRAM_DIR,"ira","ira")
            oldp=os.getcwd()
            pd = os.path.dirname(filepath)
            if pd != "":
                os.chdir(pd)
            rc = os.system(ira_path+" -a -M68020 "+os.path.basename(filepath))
            os.chdir(oldp)
            if rc != 0:
                self.__error("unable to run IRA, check that IRA executable is properly installed in %s" % ira_path)
            filepath = filepath+".asm"
            if os.path.exists(filepath):
                self.__error("Won't overwrite existing file %s" % filepath)

        asm_file = asm_parsing.AsmFile(filepath)
        self.__check_forbidden_stuff(asm_file)
        self.__check_cpu_dependent_loops(asm_file)
        self.__check_visible_self_modifying_code(asm_file)
        self.__check_invisible_self_modifying_code(asm_file)

    def __doit(self):
        # main processing here
        for f in self.__input_files:
            self.__message("Processing %s" % f)
            self.__process_file(f)

if __name__ == '__main__':
    """
        Description :
            Main application body
    """


    o = M68kChecker()
    o.init_from_sys_args(debug_mode = True)
    #o.init("output_file")
