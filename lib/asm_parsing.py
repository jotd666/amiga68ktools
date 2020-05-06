import os
import sys
import re
import fnmatch
import copy
import hashlib

#import _count_usage

class AddressingMode:
    IMMEDIATE = 0
    INDIRECT = 1
    DIRECT = 2
    REGISTER = 3
    NONE = 4

    STRINGS = ["imm","ind","direct","reg","none"]

class AsmBuffer:
    class Constant:
        def __init__(self,name,value):
            self.name = name.upper()
            self.value = value
        def __str__(self):
            return self.name+" = "+str(self.value)

    class Section:
        def __init__(self,name,section_type):
            self.name = name.upper()
            self.section_type = section_type.lower()

        def __str__(self):
            return "\tSECTION\t"+self.name+","+self.section_type.upper()   # TODO: extra params (CHIP, ...)


    class Operand:
        def __init__(self,addressing_mode,tokens,offset = 0,prepost_operation = ""):
            self.addressing_mode = addressing_mode
            self.write = False  # computed by the "Instruction" class
            self.offset = offset
            self.token = tokens
            self.prepost_operation = prepost_operation

        def __str__(self):
            rval = ""
            if self.addressing_mode == AddressingMode.IMMEDIATE:
                rval += "#"
            if self.addressing_mode == AddressingMode.INDIRECT:
                if self.prepost_operation == '-':
                    rval += '-'
                rval += "("
                if self.offset != 0:
                    rval += str(self.offset)+","

            rval += re.sub(r"[\[\]\s']*","",str(self.token))
            if self.addressing_mode == AddressingMode.INDIRECT:
                rval += ")"
                if self.prepost_operation == '+':
                    rval += '+'
            return rval

        def uses(self,token):
            rval = False
            for t in self.token:
                if str(t) == token:
                    rval = True
                    break

            return rval

        def has_prepost(self):
            return bool(self.prepost_operation)

        def get_infos(self):
            rval = "am="+AddressingMode.STRINGS[self.addressing_mode]+",toks="+str(self.token)+",prepost="+self.prepost_operation+",write="+str(self.write)+",off=%d" % self.offset
            return rval

    class Instruction:
        __COMMENT_RE = re.compile(r";(.*)")
        __HEX_COMMENT_RE = re.compile(r"^[^;]*;\s*[A-F0-9]+:\s*([A-F0-9]+)",re.IGNORECASE)

        def is_jump_or_jsr(self):
            return self.instruction_like(["db.*","jmp","jsr","b..$"])

        def is_jump(self):
            return self.mnemonic != "bsr" and self.instruction_like(["db.*","jmp","b..$"])

        def __str__(self):
            rval = "\t%s" % self.mnemonic
            if self.size:
                rval += "."+self.size

            separator = "\t"
            for o in self.operand:
                rval += separator+str(o)
                separator = ","

            if self.comments != "":
                rval += "\t;"+self.comments

            return rval

        def get_infos(self):
            rval = "inst="+self.mnemonic+",size="+self.size+",len="+str(self.length)+",ops:"
            for o in self.operand:
                rval += " "+o.get_infos()

            return rval

        def instruction_like(self,re_list):
            rval = False
            for r in re_list:
                if re.match(r,self.mnemonic,re.IGNORECASE):
                    rval = True
                    break

            return rval

        def __init__(self,mnemonic,size_string,operands,raw_line):
            """
            mnemonic: ADD, MOVE ...
            size_string: .B,.W,.L,or None
            operands: list of Operand objects
            raw_line: useful to compute number of bytes of the instruction + operands (if available) (parsing comments)
            """
            length = 0

            m = self.__COMMENT_RE.search(raw_line)
            if m == None:
                self.comments = ""
            else:
                self.comments = m.group(1)

            m = self.__HEX_COMMENT_RE.match(raw_line)
            if m != None:
                length = len(m.group(1))/2  # len in bytes

            self.mnemonic = mnemonic.lower()
            size = ""
            if size_string == None:
                if self.instruction_like([".*st","move.*","e?or.*","and.*","add.*","sub.*","clr"]):
                    # add default size
                    size = "w"
            else:
                size = size_string[1].lower()

            self.size = size
            self.length = length
            self.operand = operands
            if len(self.operand) == 1:
                # only one operand: normally write mode, unless it is a TST instruction
                self.operand[0].write = not self.mnemonic == "tst"
            elif len(self.operand) == 2:
                # two operands: normally first is read and second is write, unless it is a BTST instruction
                self.operand[0].write = False
                self.operand[1].write = not self.instruction_like(["db.*","btst","cmp"])


    # (?P<offset>re)


    __VALUE_RE = r"([\._A-Z][A-Z0-9_][A-Z0-9_]+\+\d+|[\._A-Z][A-Z0-9_][A-Z0-9_]+|\$?-?[A-F0-9]+(?:\.W)?)"     # ex: $1234, LAB_4566, EXT_3455
    __OFFSET_RE = r"(-?\$?[A-F0-9]+|[_A-Z][A-Z0-9_][A-Z0-9_]+\+\d+|-?[\._A-Z][A-Z0-9_][A-Z0-9_]+)"     # ex: $1234, LAB_4566, EXT_3455, LAB_1234+2
    __INSTRUCTION_NOPARAMS_RE = r"^\s+([A-Z]+[A-Z0-9]*)"   # ex: RTS
    __INSTRUCTION_RE = __INSTRUCTION_NOPARAMS_RE+"(\.[BLWS])?\s+(?:"   # ex: MOVE.W
    __INDIRECT_OPERAND_RE = r"(\-)?\((A[0-7]|SP)\)(\+)?|"+__OFFSET_RE+r"?\(([^)]+)\)"  # priority to (A0)+, etc... then offsets notation, else conflict
    #__REGISTER_OPERAND_RE = r"([AD][0-7]|SR|SP|VBR|CACR)"
    __REGISTER_OPERAND_RE = r"((?:[AD][0-7]|SR|SP|VBR|CACR)(?:[-/][AD][0-7]){0,15})"  # more complete, specially for multi-register parameter
    __DIRECT_OPERAND_RE = __VALUE_RE
    __IMMEDIATE_OPERAND_RE = "#"+__OFFSET_RE

    __OP_SEPARATION_RE = ")\s*,\s*(?:"        # using non-grouping parenthesis to avoid repeats in groups


    __LABEL_RE = re.compile(r"^([\.A-Z_]+[A-Z0-9_]*):?",re.IGNORECASE)
    __EQ_RE = re.compile(r"^([^\s]*)\s*(?:EQU|=)\s*(.*)",re.IGNORECASE)
    __SECTION_RE = re.compile(r"^\s+SECTION\s+([A-Z0-9_]*),([A-Z0-9_]*)",re.IGNORECASE)

    __OP1_IMMEDIATE_OP2_DIRECT = re.compile(__INSTRUCTION_RE+__IMMEDIATE_OPERAND_RE+__OP_SEPARATION_RE+__DIRECT_OPERAND_RE+r"\b)",re.IGNORECASE)
    __OP1_INDIRECT_OP2_INDIRECT = re.compile(__INSTRUCTION_RE+__INDIRECT_OPERAND_RE+__OP_SEPARATION_RE+__INDIRECT_OPERAND_RE+r")",re.IGNORECASE)
    __OP1_IMMEDIATE_OP2_INDIRECT = re.compile(__INSTRUCTION_RE+__IMMEDIATE_OPERAND_RE+__OP_SEPARATION_RE+__INDIRECT_OPERAND_RE+r")",re.IGNORECASE)
    __OP1_IMMEDIATE_OP2_REGISTER = re.compile(__INSTRUCTION_RE+__IMMEDIATE_OPERAND_RE+__OP_SEPARATION_RE+__REGISTER_OPERAND_RE+r"\b)",re.IGNORECASE)
    __OP1_DIRECT_OP2_REGISTER = re.compile(__INSTRUCTION_RE+__DIRECT_OPERAND_RE+__OP_SEPARATION_RE+__REGISTER_OPERAND_RE+r"\b)",re.IGNORECASE)
    __OP1_REGISTER_OP2_DIRECT = re.compile(__INSTRUCTION_RE+__REGISTER_OPERAND_RE+__OP_SEPARATION_RE+__DIRECT_OPERAND_RE+r"\b)",re.IGNORECASE)
    __OP1_REGISTER_OP2_INDIRECT = re.compile(__INSTRUCTION_RE+__REGISTER_OPERAND_RE+__OP_SEPARATION_RE+__INDIRECT_OPERAND_RE+r")",re.IGNORECASE)
    __OP1_REGISTER_OP2_REGISTER = re.compile(__INSTRUCTION_RE+__REGISTER_OPERAND_RE+__OP_SEPARATION_RE+__REGISTER_OPERAND_RE+r"\b)",re.IGNORECASE)
    __OP1_REGISTER = re.compile(__INSTRUCTION_RE+__REGISTER_OPERAND_RE+r")\b([^\s;]*)",re.IGNORECASE)
    __OP1_INDIRECT = re.compile(__INSTRUCTION_RE+__INDIRECT_OPERAND_RE+r")([^\s;]*)",re.IGNORECASE)
    __OP1_DIRECT = re.compile(__INSTRUCTION_RE+__DIRECT_OPERAND_RE+r")([^\s;]*)",re.IGNORECASE)
    __OP1_INDIRECT_OP2_REGISTER = re.compile(__INSTRUCTION_RE+__INDIRECT_OPERAND_RE+__OP_SEPARATION_RE+__REGISTER_OPERAND_RE+r"\b)",re.IGNORECASE)
    __OP_NONE = re.compile(__INSTRUCTION_NOPARAMS_RE,re.IGNORECASE)

    class LineDict():
        def __init__(self):
            self.label = dict()
            self.constant = dict()
            self.section = dict()
            self.instruction = dict()
            self.other = dict()

        def addresses(self):
            s = set(self.label.keys()).union(self.constant.keys(),self.section.keys(),self.instruction.keys(),self.other.keys())
            rval = list(s)
            return rval

        def get(self,address):
           if address in self.label:
               return self.label[address]
           elif address in self.instruction:
               return self.instruction[address]
           elif address in self.constant:
               return self.constant[address]
           elif address in self.section:
               return self.section[address]
           else:
               return self.other[address]

    def __init__(self,lines,filename="*buffer*"):
        """
        initialize AsmBuffer
        """

        self.__lines = []   # raw lines

        self.filename = filename
        self.linedict = self.LineDict()         # list of objects, key = address (line number)
        self.constant_value = dict()     # list of equates, key = name, value = constant value
        self.label_address = dict()     # key = label, value = address (line number)

        # maybe there are some others... we'll see

        self.__build_tokens(lines)

        k = sorted(self.linedict.instruction)

        self.__last_instruction_address = k[-1]
        self.__instruction_addresses = set(k)

    def get_instruction_addresses(self):
        return self.__instruction_addresses

    def is_instruction(self,address):
        return address in self.linedict.instruction

    def get_instruction(self,address):
        return self.linedict.instruction[address]

    def get_next_instruction(self,address):
        na = self.get_next_instruction_address(address)
        if na == -1:
            return None
        else:
            return self.get_instruction(na)

    def get_next_instruction_address(self,address):
        """
        return next line number containing an instruction
"""
        rval = -1
        for i in range(address+1,self.__last_instruction_address):
            if i in self.__instruction_addresses:
                rval = i
                break
        return rval

    def get_prev_instruction_address(self,address):
        """
        return prev line number containing an instruction
"""
        rval = -1
        for i in range(address-1,0,-1):
            if i in self.__instruction_addresses:
                rval = i
                break
        return rval

    def get_raw_lines(self):
        return self.__lines

    def get_raw_line(self,linenum):

        if linenum < len(self.__lines):
            rval = self.__lines[linenum].replace("\n","")
        return rval

    def parse_number(self,n):
        """
convert to decimal if possible
"""
        rval = n
        if n[0] == "$":
            rval = int(n[1:],16)
        else:
            try:
                rval = int(n)
            except:
                pass
        return rval

    def __build_indirect_operand(self,groups):
        offset = 0
        prepost_operation = ""
        if groups[1] == None:
            # with offset
            if groups[3] != None:
                offset = self.parse_number(groups[3])

            tokens = groups[4].split(",")
        else:
            # pre-post op
            tokens = [groups[1]]

            if groups[0]:
                prepost_operation = groups[0]
            elif groups[2]:
                prepost_operation = groups[2]

        o = self.Operand(AddressingMode.INDIRECT,tokens,offset,prepost_operation)

        return o

    def __add_constant(self,address,name,value):
        c = self.Constant(name,value)
        self.constant_value[c.name] = c.value
        self.linedict.constant[address] = c
        return c

    def __add_instruction(self,address,instruction):
        self.linedict.instruction[address] = instruction

    def __add_other(self,address,line):
        self.linedict.other[address] = line

    def __add_section(self,address,name,section_type):
        c = self.Section(name,section_type)
        self.linedict.section[address] = c
        return c

    def __add_label(self,address,name):
        self.linedict.label[address] = name
        self.label_address[name] = address      # reverse lookup

    def __build_tokens(self,f):
        count = -1
        section_type = "code"   # default
        section_name = ""

        for l in f:
            count += 1
            m = None
            raw_line = l
            self.__lines.append(raw_line)
            # remove trailing comments
            l = re.sub(r"\s*;.*","",l)
            if l.strip() != "":
                #print "RAW: ",raw_line.strip()

                if m == None:
                    m = self.__EQ_RE.search(l)
                    if m != None:
                        # this is an EQ expression, not an instruction
                        # add a constant
                        self.__add_constant(count,m.group(1),self.parse_number(m.group(2)))
                        continue

                if m == None:
                    m = self.__SECTION_RE.search(l)
                    if m != None:
                        # this is an EQ expression, not an instruction

                       s = self.__add_section(count,m.group(1),m.group(2))
                       section_name = s.name
                       section_type = s.section_type
                       continue


                if m == None:
                    m = self.__LABEL_RE.search(l)
                    if m != None:
                        # this is a label, not an instruction
                        self.__add_label(count,m.group(1))
                        continue

                if section_type == "code":
                    instruction = None
                    if m == None:
                        m = self.__OP1_DIRECT.search(l)
                        if m != None:
                            if m.groups()[-1].find(",") == -1:
                                # build instruction with only 1 register
                                o1 = self.Operand(AddressingMode.DIRECT,[m.group(3)])
                                instruction = self.Instruction(m.group(1),m.group(2),[o1],raw_line)
                            else:
                                m = None
                    if m == None:
                        m = self.__OP1_REGISTER.search(l)
                        if m != None:
                            if m.groups()[-1].find(",") == -1:
                                # build instruction with only 1 register
                                o1 = self.Operand(AddressingMode.REGISTER,[m.group(3)])
                                instruction = self.Instruction(m.group(1),m.group(2),[o1],raw_line)
                            else:
                                m = None

                    if m == None:
                        m = self.__OP1_INDIRECT.search(l)
                        if m != None:
                            if m.groups()[-1].find(",") == -1:
                                # build instruction with only 1 register
                                o1 = self.__build_indirect_operand(m.groups()[2:])

                                instruction = self.Instruction(m.group(1),m.group(2),[o1],raw_line)
                            else:
                                m = None


                    if m == None:
                        m = self.__OP1_IMMEDIATE_OP2_INDIRECT.search(l)
                        if m != None:
                            o1 = self.Operand(AddressingMode.IMMEDIATE,[self.parse_number(m.group(3))])
                            o2 = self.__build_indirect_operand(m.groups()[3:])
                            instruction = self.Instruction(m.group(1),m.group(2),[o1,o2],raw_line)

                    if m == None:
                        m = self.__OP1_REGISTER_OP2_INDIRECT.search(l)
                        if m != None:
                                # build instruction with 2 registers
                                o1 = self.Operand(AddressingMode.REGISTER,[m.group(3)])
                                o2 = self.__build_indirect_operand(m.groups()[3:])
                                instruction = self.Instruction(m.group(1),m.group(2),[o1,o2],raw_line)
                    if m == None:
                        m = self.__OP1_REGISTER_OP2_REGISTER.search(l)
                        if m != None:
                                # build instruction with 2 registers
                                o1 = self.Operand(AddressingMode.REGISTER,[m.group(3)])
                                o2 = self.Operand(AddressingMode.REGISTER,[m.group(4)])
                                instruction = self.Instruction(m.group(1),m.group(2),[o1,o2],raw_line)

                    if m == None:
                        m = self.__OP1_INDIRECT_OP2_INDIRECT.search(l)
                        if m != None:
                                # build instruction with 2 indirects
                                o1 = self.__build_indirect_operand(m.groups()[2:])
                                o2 = self.__build_indirect_operand(m.groups()[7:])
                                instruction = self.Instruction(m.group(1),m.group(2),[o1,o2],raw_line)

                    if m == None:
                        m = self.__OP1_IMMEDIATE_OP2_REGISTER.search(l)
                        if m != None:
                            o1 = self.Operand(AddressingMode.IMMEDIATE,[self.parse_number(m.group(3))])
                            o2 = self.Operand(AddressingMode.REGISTER,[m.group(4)])
                            instruction = self.Instruction(m.group(1),m.group(2),[o1,o2],raw_line)

                    if m == None:
                        m = self.__OP1_IMMEDIATE_OP2_DIRECT.search(l)
                        if m != None:
                            o1 = self.Operand(AddressingMode.IMMEDIATE,[self.parse_number(m.group(3))])
                            o2 = self.Operand(AddressingMode.DIRECT,[m.group(4)])
                            instruction = self.Instruction(m.group(1),m.group(2),[o1,o2],raw_line)


                    if m == None:
                        m = self.__OP1_DIRECT_OP2_REGISTER.search(l)
                        if m != None:
                            o1 = self.Operand(AddressingMode.DIRECT,[m.group(3)])
                            o2 = self.Operand(AddressingMode.REGISTER,[m.group(4)])
                            instruction = self.Instruction(m.group(1),m.group(2),[o1,o2],raw_line)

                    if m == None:
                        m = self.__OP1_REGISTER_OP2_DIRECT.search(l)
                        if m != None:
                            o1 = self.Operand(AddressingMode.REGISTER,[m.group(3)])
                            o2 = self.Operand(AddressingMode.DIRECT,[m.group(4)])
                            instruction = self.Instruction(m.group(1),m.group(2),[o1,o2],raw_line)

                    if m == None:
                        m = self.__OP1_INDIRECT_OP2_REGISTER.search(l)
                        if m != None:
                                # build instruction with indirect to register
                                o1 = self.__build_indirect_operand(m.groups()[2:])
                                o2 = self.Operand(AddressingMode.REGISTER,[m.group(8)])
                                instruction = self.Instruction(m.group(1),m.group(2),[o1,o2],raw_line)

                    if m == None:
                        m = self.__OP_NONE.search(l)
                        if m != None:
                            # no parameters
                            instruction = self.Instruction(m.group(1),None,[],raw_line)

                    if m == None:
                        # unmatched
                        raise Exception("unmatched instruction %s at line %d" % (l.strip(),count))

                    if instruction != None:
                        self.__add_instruction(count,instruction)
                        continue

            # fallback: add the raw line
            self.__add_other(count,raw_line)


class AsmFile(AsmBuffer):
     def __init__(self,filepath):
         self.filepath = filepath
         filename = os.path.basename(filepath)

         f = open(self.filepath,"rt")
         AsmBuffer.__init__(self,f,filename)
         f.close()



def assert_eq(s,ref):
    if s != ref:
##        if ref == None or s == None:
##            if s != None:
##            print "*** eq failed: "
##        else:
            print("*** eq failed: %s != %s" % (s,ref))

def selftest():
    buf = """start:
    MOVE.L  D0,D1      ; 0000: AABB reg,reg
    MOVE.W  (A0),D2     ; 0002: CCDD indirect,reg
    MOVE  $12340,D3     ; 0004: 23FC00012340 direct,reg
    MOVE  $1234.W,D3    ; direct,reg
    MOVE.L  #12,data+2
    MOVE.L  #14,data
    MOVE.L  LAB_1234+2,D3   ; direct,reg
loop:
    MOVE.L  12(A0),D1       ; indirect,reg
    MOVE.L  (A0)+,D1        ; indirect,reg
    MOVE.L  12(A0,D0),$14(A0,D1) ; indirect,indirect
    MOVE.W  -(A0),(A1)+         ; indirect,indirect
    TST.L   D1                  ; 0012: 4433 reg
    ST   D1                  ; 0012: 4433 reg
    DBNE    D0,loop         ; special
    moveq.l #0,d0
    MOVE.W  D2,$4544     ; 0002: CCDD indirect,reg
    JMP (A0)
    TST.L $12354
    RTS                     ; 0014: 4E75
data:
    DC.B    0,4,5,3

"""
    buf = """DMACON  = $DFF096
COPCON EQU $DFF080
PIPO EQU 12
    SECTION S_D,DATA,CHIP
    dc.b    ksdksjdk,skdjksjdks,sjdksjd
    ; this sucks
    SECTION S_0,CODE
	BCLR	#0,(-1,A5)		;0052A: 08AD0000FFFF
	MOVEA.L	LAB_00C5(PC),22(A4)		;01A7E: 287AFDAA
    CLR.B   -(A7)

"""


    a = AsmBuffer(buf.splitlines())

    addresses = a.linedict.addresses()

    # dump everything
    for i in addresses:
        s = a.linedict.get(i)
        print(str(s))
    print("===========")
    # dump only instructions

    ia = a.get_instruction_addresses()
    for i in ia:
        print(str(a.get_instruction(i)))

##    print a.label
##    print a.constant
##    print a.section

if __name__ == '__main__':
    global program_name
    program_name = os.path.basename(sys.argv[0])

    selftest();

