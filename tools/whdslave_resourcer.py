#!/usr/bin/python

# coded by JOTD (C) 2016-2019

import os,sys,re,subprocess
import getopt,traceback
import glob,shutil


# TODO
# first pass to mark patchlists with NOPs and re-run disassembly, work from there!!!!!
# detect Control tag pointer and convert tag enums
# final comment cleanup regex: \s+;[0-9a-f]{2,}:.*

MRK_NONE = 0
MRK_CODE = 1
MRK_DATA = 2
MRK_PATCHLIST = 3
MRK_HEADER = 4

SLAVE_FUTURE_VERSION = 17

try:
    unicode
    ord2 = ord
except NameError:
    ord2 = lambda x:x

class WrongPatchArgException(Exception):
    pass

class WHDSlaveResourcer:
    __VERSION_NUMBER = "0.91"
    __MODULE_FILE = __file__
    __PROGRAM_NAME = os.path.basename(__MODULE_FILE)
    __PROGRAM_DIR = os.path.abspath(os.path.dirname(__MODULE_FILE))

    def __init__(self):
        self.__logfile = ""
        self.__current_slave_file = "No slave"
        # init members with default values
        self.__output_file = ""
        self.__input_files = []
        #self.__deep_patchlist = False


    def init_from_sys_args(self,debug_mode = True):
        """ standalone mode """

        try:
            self.__do_init()
        except Exception:
            traceback.print_exc()
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
            f = open(self.__logfile,"ab")
            f.write(msg)
            f.close()

    def __error(self,msg):
        raise Exception("Error: %s (%s)" % (msg,self.__current_slave_file))

    def __warn(self,msg):
        self.__message("Warning: "+msg)

    def __parse_args(self):
         # Command definition
         # Prepare short & long args from list to avoid duplicate info

        self.__opt_string = ""

        longopts_eq = ["version","help","input-file="] #,"deep-patchlist"]

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
            oi += 1
##            if option in ('-d','--'+self.__longopts[oi]):
##                self.__deep_patchlist = True

        if len(self.__input_files) == 0:
            self.__error("no input files")

    def __usage(self):

        sys.stderr.write("Usage: "+self.__PROGRAM_NAME+self.__opt_string+os.linesep)

    __RESLOAD_FUNCTION_RE = re.compile(r"^\s*\w+\s+resload_(\w+)")
    __ABORT_REASON_RE = re.compile(r"(TDREASON_\w+)\s+=\s*(-?\d+)")


    __ABORT_CODES = """
TDREASON_OK  = -1
TDREASON_DOSREAD	= 1	;error caused by resload_ReadFile
				; primary   = dos errorcode
				; secondary = file name
TDREASON_DOSWRITE	= 2	;error caused by resload_SaveFile or
				;resload_SaveFileOffset
				; primary   = dos errorcode
				; secondary = file name
TDREASON_DEBUG		= 5	;cause WHDLoad to make a coredump and quit
				; primary   = PC (to be written to dump files)
				; secondary = SR (to be written to dump files)
TDREASON_DOSLIST	= 6	;error caused by resload_ListFiles
				; primary   = dos errorcode
				; secondary = directory name
TDREASON_DISKLOAD	= 7	;error caused by resload_DiskLoad
				; primary   = dos errorcode
				; secondary = disk number
TDREASON_DISKLOADDEV	= 8	;error caused by resload_DiskLoadDev
				; primary   = trackdisk errorcode
TDREASON_WRONGVER	= 9	;an version check (e.g. CRC16) has detected an
				;unsupported version of the installed program
TDREASON_OSEMUFAIL	= 10	;error in the OS emulation module
				; primary   = subsystem (e.g. "exec.library")
				; secondary = error number (e.g. _LVOAllocMem)
; version 7
TDREASON_REQ68020	= 11	;installed program requires a MC68020
TDREASON_REQAGA		= 12	;installed program requires the AGA chip set
TDREASON_MUSTNTSC	= 13	;installed program needs NTSC video mode to run
TDREASON_MUSTPAL	= 14	;installed program needs PAL video mode to run
; version 8
TDREASON_MUSTREG	= 15	;WHDLoad must be registered
TDREASON_DELETEFILE	= 27	;error caused by resload_DeleteFile
				; primary   = dos errorcode
				; secondary = file name
; version 14.1
TDREASON_FAILMSG	= 43	;fail with a slave defined message text
				; primary   = text""".split("\n")

    __RESLOAD_FUNCTIONS = """
	ULONG	resload_Install		;private
	ULONG	resload_Abort
		; return to operating system (4)
		; IN: (a7) = ULONG  reason for aborting
		;   (4,a7) = ULONG  primary error code
		;   (8,a7) = ULONG  secondary error code
		; ATTENTION: this routine must be called via JMP (not JSR)
	ULONG	resload_LoadFile
		; load file to memory (8)
		; IN:	a0 = CSTR   filename
		;	a1 = APTR   address
		; OUT:	d0 = ULONG  success (size of file)
		;	d1 = ULONG  dos errorcode
	ULONG	resload_SaveFile
		; write memory to file (c)
		; IN:	d0 = ULONG  size
		;	a0 = CSTR   filename
		;	a1 = APTR   address
		; OUT:	d0 = BOOL   success
		;	d1 = ULONG  dos errorcode
	ULONG	resload_SetCACR
		; set cachebility for BaseMem (10)
		; IN:	d0 = ULONG  new setup
		;	d1 = ULONG  mask
		; OUT:	d0 = ULONG  old setup
	ULONG	resload_ListFiles
		; list filenames of a directory (14)
		; IN:	d0 = ULONG  buffer size
		;	a0 = CSTR   name of directory to scan
		;	a1 = APTR   buffer (must be located inside Slave,
		;	with WHDLoad 16.8+ also inside ExpMem)
		; OUT:	d0 = ULONG  amount of names in buffer filled
		;	d1 = ULONG  dos errorcode
	ULONG	resload_Decrunch
		; uncompress data in memory (18)
		; IN:	a0 = APTR   source
		;	a1 = APTR   destination (can be equal to source)
		; OUT:	d0 = ULONG  uncompressed size
	ULONG	resload_LoadFileDecrunch
		; load file and uncompress it (1c)
		; IN:	a0 = CSTR   filename
		;	a1 = APTR   address
		; OUT:	d0 = ULONG  success (size of file uncompressed)
		;	d1 = ULONG  dos errorcode
	ULONG	resload_FlushCache
		; clear CPU caches (20)
		; IN:	-
		; OUT:	-
	ULONG	resload_GetFileSize
		; get size of a file (24)
		; IN:	a0 = CSTR   filename
		; OUT:	d0 = ULONG  size of file
	ULONG	resload_DiskLoad
		; load part from disk image (28)
		; IN:	d0 = ULONG  offset
		;	d1 = ULONG  size
		;	d2 = ULONG  disk number
		;	a0 = APTR   destination
		; OUT:	d0 = BOOL   success
		;	d1 = ULONG  dos errorcode

******* the following functions require ws_Version >= 2

	ULONG	resload_DiskLoadDev
		; load part from physical disk via trackdisk (2c)
		; IN:	d0 = ULONG  offset
		;	d1 = ULONG  size
		;	a0 = APTR   destination
		;	a1 = STRUCT taglist
		; OUT:	d0 = BOOL   success
		;	d1 = ULONG  trackdisk errorcode

******* the following functions require ws_Version >= 3

	ULONG	resload_CRC16
		; calculate 16 bit CRC checksum (30)
		; IN:	d0 = ULONG  size
		;	a0 = APTR   address
		; OUT:	d0 = UWORD  CRC checksum

******* the following functions require ws_Version >= 5

	ULONG	resload_Control
		; misc control, get/set variables (34)
		; IN:	a0 = STRUCT taglist
		; OUT:	d0 = BOOL   success
	ULONG	resload_SaveFileOffset
		; write memory to file at offset (38)
		; IN:	d0 = ULONG  size
		;	d1 = ULONG  offset
		;	a0 = CSTR   filename
		;	a1 = APTR   address
		; OUT:	d0 = BOOL   success
		;	d1 = ULONG  dos errcode

******* the following functions require ws_Version >= 6

	ULONG	resload_ProtectRead
		; mark memory as read protected (3c)
		; IN:	d0 = ULONG  length
		;	a0 = APTR   address
		; OUT:	-
	ULONG	resload_ProtectReadWrite
		; mark memory as read and write protected (40)
		; IN:	d0 = ULONG  length
		;	a0 = APTR   address
		; OUT:	-
	ULONG	resload_ProtectWrite
		; mark memory as write protected (44)
		; IN:	d0 = ULONG  length
		;	a0 = APTR   address
		; OUT:	-
	ULONG	resload_ProtectRemove
		; remove memory protection (48)
		; IN:	d0 = ULONG  length
		;	a0 = APTR   address
		; OUT:	-
	ULONG	resload_LoadFileOffset
		; load part of file to memory (4c)
		; IN:	d0 = ULONG  size
		;	d1 = ULONG  offset
		;	a0 = CSTR   filename
		;	a1 = APTR   destination
		; OUT:	d0 = BOOL   success
		;	d1 = ULONG  dos errorcode

******* the following functions require ws_Version >= 8

	ULONG	resload_Relocate
		; relocate AmigaDOS executable (50)
		; IN:	a0 = APTR   address (source=destination)
		;	a1 = STRUCT taglist
		; OUT:	d0 = ULONG  size
	ULONG	resload_Delay
		; wait some time or button pressed (54)
		; IN:	d0 = ULONG  time to wait in 1/10 seconds
		; OUT:	-
	ULONG	resload_DeleteFile
		; delete file (58)
		; IN:	a0 = CSTR   filename
		; OUT:	d0 = BOOL   success
		;	d1 = ULONG  dos errorcode

******* the following functions require ws_Version >= 10

	ULONG	resload_ProtectSMC
		; detect self modifying code (5c)
		; IN:	d0 = ULONG  length
		;	a0 = APTR   address
		; OUT:	-
	ULONG	resload_SetCPU
		; control CPU setup (60)
		; IN:	d0 = ULONG  properties, see above
		;	d1 = ULONG  mask
		; OUT:	d0 = ULONG  old properties
	ULONG	resload_Patch
		; apply patchlist (64)
		; IN:	a0 = APTR   patchlist, see below
		;	a1 = APTR   destination address
		; OUT:	-

******* the following functions require ws_Version >= 11

	ULONG	resload_LoadKick
		; load kickstart image (68)
		; IN:	d0 = ULONG  length of image
		;	d1 = UWORD  crc16 of image
		;	a0 = CSTR   basename of image
		; OUT:	-
	ULONG	resload_Delta
		; apply WDelta data to modify memory (6c)
		; IN:	a0 = APTR   src data
		;	a1 = APTR   dest data
		;	a2 = APTR   wdelta data
		; OUT:	-
	ULONG	resload_GetFileSizeDec
		; get size of a packed file (70)
		; IN:	a0 = CSTR   filename
		; OUT:	d0 = ULONG  size of file uncompressed

******* the following functions require ws_Version >= 15

	ULONG	resload_PatchSeg
		; apply patchlist to a segment list (74)
		; IN:	a0 = APTR   patchlist, see below
		;	a1 = BPTR   segment list
		; OUT:	-

	ULONG	resload_Examine
		; examine a file or directory (78)
		; IN:	a0 = CSTR   name
		;	a1 = APTR   struct FileInfoBlock (260 bytes)
		; OUT:	d0 = BOOL   success
		;	d1 = ULONG  dos errorcode

	ULONG	resload_ExNext
		; examine next entry of a directory (7c)
		; IN:	a0 = APTR   struct FileInfoBlock (260 bytes)
		; OUT:	d0 = BOOL   success
		;	d1 = ULONG  dos errorcode

	ULONG	resload_GetCustom
		; get Custom argument (80)
		; IN:	d0 = ULONG  length of buffer
		;	d1 = ULONG  reserved, must be 0
		;	a0 = APTR   buffer
		; OUT:	d0 = BOOL   true if Custom has fit into buffer

******* the following functions require ws_Version >= 18

	ULONG	resload_VSNPrintF
		; format string like clib.vsnprintf/exec.RawDoFmt (84)
		; IN:	d0 = ULONG  length of buffer
		;	a0 = APTR   buffer to fill
		;	a1 = CPTR   format string
		;	a2 = APTR   argument array
		; OUT:	d0 = ULONG  length of created string with unlimited
		;		    buffer without final '\0'
		;	a0 = APTR   pointer to final '\0'

	ULONG	resload_Log
		; write log message (88)
		; IN:	a0 = CSTR   format string
		;   (4,a7) = LABEL  argument array
		; OUT:	-

""".split("\n")

    __HEADER = """; Resourced by whdslave_resourcer v%s
; a program written by JOTD in 2016-2019
;
	INCDIR	Include:
	INCLUDE	whdload.i
	INCLUDE	whdmacros.i

	IFD BARFLY
	OUTPUT	"%s"
	;BOPT	O+				;enable optimizing
	;BOPT	OG+				;enable optimizing
	BOPT	ODd-				;disable mul optimizing
	BOPT	ODe-				;disable mul optimizing
	BOPT	w4-				;disable 64k warnings
	SUPER
	ENDC


_base	SLAVE_HEADER					; ws_security + ws_id
	dc.w	%d					; ws_version (was %d)
	dc.w	%s
	dc.l	$%x					; ws_basememsize
	dc.l	%d					; ws_execinstall
	dc.w	start-_base		; ws_gameloader
	dc.w	%s					; ws_currentdir
	dc.w	0					; ws_dontcache
_keydebug
	dc.b	$%x					; ws_keydebug
_keyexit
	dc.b	$%x					; ws_keyexit
_expmem
	dc.l	$%x					; ws_expmem
	dc.w	_name-_base				; ws_name
	dc.w	_copy-_base				; ws_copy
	dc.w	_info-_base				; ws_info
    dc.w    %s     ; kickstart name
    dc.l    $%x         ; kicksize
    dc.w    $%x         ; kickcrc
    dc.w    _config-_base
;---
_config
;	dc.b	"BW;"
; dc.b    "C1:X:Infinite lives:0;"

	dc.b	0

	IFD BARFLY
	DOSCMD	"WDate  >T:date"
	ENDC

DECL_VERSION:MACRO
	dc.b	"2.0"
	IFD BARFLY
		dc.b	" "
		INCBIN	"T:date"
	ENDC
	IFD	DATETIME
		dc.b	" "
		incbin	datetime
	ENDC
	ENDM
_data   dc.b    '%s',0
_name	dc.b	'%s',0
_copy	dc.b	'%s',0
_info
%s
_kickname   dc.b    '%s',0
;--- version id

    dc.b	%s
    even
"""
    def __asm_string(self,s):
        rval = "    dc.b   "
        was_ascii = False
        for c in s:
            oc = ord(c)
            if oc>31:
                if was_ascii:
                    pass
                else:
                    rval += "'"
                rval += c
                was_ascii = True
            else:
                if was_ascii:
                    rval += "'"
                rval += ","+str(oc)+","
                was_ascii = False
        if was_ascii:
            rval += "'"
        rval += ",0"
        return re.sub(",+",",",rval)

    def __create_temp_directory(self):
        self.__temp_directory = os.path.join(os.getenv("TEMP","T:"),os.path.splitext(self.__PROGRAM_NAME)[0])
        if os.path.exists(self.__temp_directory):
            pass
        else:
            os.mkdir(self.__temp_directory)
        return self.__temp_directory


    def __get_be_short(self,offset,signed=False):
        rval = (ord2(self.__slave[offset])<<8)+ord2(self.__slave[offset+1])
        if signed and rval>0x7FFF:
            # negative
            rval = - ((~rval + 1) % (0x10000))
        return rval

    def __get_byte(self,offset):
        return ord2(self.__slave[offset])

    def __get_byte_as_hex_string(self,offset):
        o = self.__get_byte(offset)
        return "$%02x" % o

##    def __get_byte_as_string(self,offset):
##        o = self.__get_byte(offset)
##        if o>31 and o<127:
##            rval = "'"+chr(o)+"'"
##        else:
##            rval = "$%02x" % o
##        return rval

    def __get_be_long(self,offset):
        return (self.__get_be_short(offset,False)<<16) + self.__get_be_short(offset+2,False)

    def __repl_abort_code(self,m):
        v = m.group(2)
        idx = int(v.replace(".W",""))

        abort_code = self.__tdreason_dict.get(idx,v)
        return m.group(1)+abort_code

    def __get_string(self,offset,length):
        return self.__slave[offset:offset+length]
    def __get_c_string(self,offset):
        i = offset
        while True:
            if ord2(self.__slave[i])==0:
                break
            i+=1
        return self.__slave[offset:i].replace(b"\xff",b"\n").decode("ascii","ignore")

    __WDATE_RE = re.compile(r"\(\d\d\-[a-z]+\-\d\d\s+\d\d:\d\d:\d\d\)")
    __OFFSET_RE = re.compile(";([0-9a-f]+)")
    __NOP_OFFSET_RE = re.compile("NOP.*;([0-9a-f]+):")
    __LABEL_RE = re.compile("^(LAB_.*?):")

    __LABEL_IN_CODE_RE = re.compile("(LAB_....)")
    __J_OFFSET_RE_1 = re.compile("(jsr|jmp)\s+(\$?[0-9a-z]+)\(a(\d)\)",re.IGNORECASE)
    __J_OFFSET_RE_2 = re.compile("(jsr|jmp)\s+(\(\$?[0-9a-z]+),a(\d)\)",re.IGNORECASE)
    __MOVE_RESLOAD_AX_RE = re.compile("move.*_resload.*,a(\d)",re.IGNORECASE)
    __PEA_VALUE_RE = re.compile(r"(pea\s+)(-?\d+\.?W?)",re.IGNORECASE)
    __PUSH_VALUE_RE = re.compile(r"(move.*\s+#)(\d+)",re.IGNORECASE)
    __MODIFY_AX_RE = re.compile(r"\s+\w+.*\s+([^\s]*),a(\d)\s*;",re.IGNORECASE) # fuzzy, but should work
    __DATE_REPL = "'\n\tINCBIN\tT:date\n\tdc.b\t'"
    __HEADER_OFFSET_DICT = { 12 : "slave_version", 14 : "flags",
        16 : "basemem_size", 30 : "_keydebug", 31 : "_keyexit", 32: "_expmem"}  # expmem = expmem_size at startup
    __ASM_LINE_RE = re.compile("\t([\w\.]+)\s+(.*[^\s])\s+;.*")
    __DCW_LINE_RE = re.compile("\tDC\.W\s+\$(....)\s+;.*")
    __ASM_LINE_NOARG_RE = re.compile("\t(\w+)\s+;.*")
    __DCB_FMT = "\tDC.B\t$%x\t;%x"

    class Instruction():
        def __init__(self,kind=MRK_NONE):
            self.line = None
            self.label = None
            self.kind = kind


    def __get_next_instruction_offset(self,current_offset):
        # lame, replace by bisect to improve performance
        rval = None
        for i,offset in enumerate(self.__offset_keys):
            if offset==current_offset:
                rval =  self.__offset_keys[i+1]
                break
        return rval

    def __get_label_offset(self,label):

        if label in self.__code_labels:
            rval = self.__code_labels[label]
        else:
            # simple expression lab+xxx
            e = label.split("+")
            if len(e)==2:
                rval = self.__get_label_offset(e[0]) + int(e[1])
            else:
                raise Exception("Cannot compute offset for expression %d" % label)
        return rval

    def __mark_zone(self,offset,length,mark_type):
        for i in range(offset,offset+length):
            self.__code_table[i].kind = mark_type

    def __mark_code(self,entry_offset):
        current_offset = entry_offset
        while 0 < current_offset < len(self.__code_table) and self.__code_table[current_offset].kind==MRK_NONE:

            self.__code_table[current_offset].kind = MRK_CODE
            self.__code_table[current_offset+1].kind = MRK_CODE

            code = self.__code_table[current_offset]
            if code.line==None:
                if not self.last_pass:
                    self.__warn("No code at offset $%x" % current_offset)
                    return
                else:
                    raise Exception("Pass %d: No code at offset $%x" % (self.pass_count,current_offset))

            m = re.match(self.__ASM_LINE_RE,code.line)
            if m==None:
                m = re.match(self.__ASM_LINE_NOARG_RE,code.line)
            if m==None:
                msg = "Offset %x: no code: %s" % (current_offset,code.line)
                if self.last_pass:
                    raise Exception(msg)
                else:
                    self.__warn(msg)
                    return

            if m.group(1) in ["RTS","RTE","JMP"]:
                # break sequence (JMP & JSR are probably jump tables: cannot go further)
                break
            elif m.group(1)[0]=='B':
                mnem = m.group(1).split(".")[0]
                if len(mnem)==3:
                    # branch instruction
                    target = m.group(2)
                    branch_offset = self.__get_label_offset(target)
                    if branch_offset % 2==0:
                        self.__mark_code(branch_offset)     # recursion
                    if mnem=="BRA": # break sequence, else continue since there is code behind the conditional branch
                        break
            # next instruction: compute next
            next_offset = self.__get_next_instruction_offset(current_offset)
            if next_offset==None:
                break  # not expected
            if next_offset<current_offset or next_offset>current_offset+10:
                # problem
                raise Exception("Offset %x: next instruction too far: %x, %s" % (current_offset,next_offset,code.line) )
            for i in range(current_offset+2,next_offset):
                self.__code_table[i].kind = MRK_CODE
            current_offset = next_offset


    def __is_unmarked(self,start,length):
        rval = True
        for i in range(start,start+length):
            if self.__code_table[i].kind != MRK_NONE:
                rval = False
                break
        return rval

    def __decode_patch_arg(self,arg):
        rval = None

        if isinstance(arg,int):
            rval = "$%x" % arg # second arg is always a value
        elif isinstance(arg,list):
            value = arg[0]
            if arg[1]:
                # address, within slave: create the label if does not exist
                if len(self.__code_table) <= value or value < 0:
                    raise WrongPatchArgException("address out of slave")

                instruction = self.__code_table[value]
                if instruction.label==None:
                    #if value%2:
                        # odd: get previous label (may crash, will see later)
                    #    instruction.label = self.__code_table[value-1].label+"+1"
                    #else:
                        # create label
                        instruction.label = "LABN_%04X" % value
                rval = instruction.label
            else:
                if value > 10:
                    rval = "$%x" % value
                else:
                    rval = str(value)

        else:
            raise WrongPatchArgException("Wrong patch arg: %s" % arg)
        return rval

    def __decode_abort(self,end,start,step):
        """
        decode normal abort call
        """
        for bl in range(end,start,-2):
            preab_instruction = self.__code_table[bl]
            l=""
            if preab_instruction.line:
                l = preab_instruction.line
                l = re.sub(self.__PEA_VALUE_RE,self.__repl_abort_code,l)
                if l!=preab_instruction.line:
                    preab_instruction.line=l
                    #break

            else:
                l = re.sub(self.__PUSH_VALUE_RE,self.__repl_abort_code,l)
                if l!=preab_instruction.line:
                    preab_instruction.line = l
                    #break

    def __decode_abort_2(self,end,start):
        """
        multiple pea ending by pushing resload and RTS
        """
        for bl in range(end,start,-1):
            preab_instruction = self.__code_table[bl]
            l=""
            if preab_instruction.line:
                l = preab_instruction.line
                l = re.sub(self.__PEA_VALUE_RE,self.__repl_abort_code,l)
                if l!=preab_instruction.line:
                    preab_instruction.line=l

            else:
                l = re.sub(self.__PUSH_VALUE_RE,self.__repl_abort_code,l)
                if l!=preab_instruction.line:
                    preab_instruction.line = l

    def __process_file(self):

        slave_basename = os.path.basename(self.__current_slave_file)
        f = open(self.__current_slave_file,"rb")

        raw_input_data = f.read()
        f.close()

        self.__slave = raw_input_data
        if self.__get_be_long(0) != 0x3F3:
            self.__error("Not an executable")

        # from now on skip header so offset is correct
        self.__slave = self.__slave[0x20:]

        if self.__get_string(0x4,8)!=b"WHDLOADS":
            self.__error("Executable is not a whdload slave")


        slave_version = self.__get_be_short(12)
        flags = self.__get_be_short(14)
        basemem_size = self.__get_be_long(16)
        exec_install = self.__get_be_long(20)
        entry_offset = self.__get_be_short(24)
        current_dir_offset = self.__get_be_short(26)
        dont_cache = self.__get_be_short(28)
        key_debug = self.__get_byte(30)
        key_exit = self.__get_byte(31)
        expmem_size = self.__get_be_long(32) if slave_version > 7 else 0

        kick_string = ""
        current_dir_string = ""
        if current_dir_offset > 0:
            current_dir_string = self.__get_c_string(current_dir_offset)
        info_string = "?"
        game_name = os.path.splitext(slave_basename)[0]  # default
        copyright_string = "?"
        kickname_offset = 0
        kick_crc = 0
        kick_size = 0
        if slave_version>9:
            name_offset = self.__get_be_short(0x24)
            game_name = self.__get_c_string(name_offset)
            copy_offset = self.__get_be_short(0x26)
            copyright_string = self.__get_c_string(copy_offset)
            info_offset = self.__get_be_short(0x28)
            info_string = self.__WDATE_RE.sub("*THEDATE*",self.__get_c_string(info_offset))

        if slave_version>15:
            kickname_offset = self.__get_be_short(0x2A)
            if kickname_offset>0:
                kick_string = self.__get_c_string(kickname_offset)
            kick_size = self.__get_be_long(0x2C)
            kick_crc = self.__get_be_short(0x30)

        version_offset = self.__slave.find(b"$VER")
        version_id = "'',0"
        if version_offset != -1:
            version_id = "'"+self.__get_c_string(version_offset)+"',0"
            version_id = self.__WDATE_RE.sub(self.__DATE_REPL,version_id).replace("'',0","0")    # remove hardcoded date, insert current date
        # decode flags
        opt020=""
        flags_list = []
        if flags & 1:
            flags_list.append("Disk")
        if flags & 1<<1:
            flags_list.append("NoError")
        if flags & 1<<2:
            flags_list.append("EmulTrap")
        if flags & 1<<3:
            flags_list.append("NoDivZero")
        if flags & 1<<4:
            flags_list.append("Req68020")
            opt020="-M68020"
        if flags & 1<<5:
            flags_list.append("ReqAGA")
        if flags & 1<<6:
            flags_list.append("NoKbd")
        if flags & 1<<7:
            flags_list.append("EmulLineA")
        if flags & 1<<8:
            flags_list.append("EmulTrapV")
        if flags & 1<<9:
            flags_list.append("EmulChk")
        if flags & 1<<10:
            flags_list.append("EmulPriv")
        if flags & 1<<11:
            flags_list.append("EmulLineF")
        if flags & 1<<12:
            flags_list.append("ClearMem")
        if flags & 1<<13:
            flags_list.append("Examine")
        if flags & 1<<14:
            flags_list.append("EmulDivZero")
        if flags & 1<<15:
            flags_list.append("EmulIllegal")

        flags_str = "|".join(["WHDLF_"+f for f in flags_list])
        self.__message("Slave version: %d" % slave_version)
        self.__message("Flags: %s" % flags_str)
        self.__message("Basemem size: $%08x" % basemem_size)
        self.__message("Expmem size: $%08x" % expmem_size)


        self.__message("Current dir: %s" % current_dir_string)
        self.__message("Name: %s" % game_name)
        self.__message("Info: %s" % info_string)
        self.__message("Copyright: %s" % copyright_string)
        self.__message("Quitkey: $%02x" % key_exit)
        self.__message("Debugkey: $%02x" % key_debug)
        if version_id!="":
            self.__message("Version id: %s" % version_id)
        self.__message("Entry offset : $%x" % entry_offset)

        current_dir_dc = "0"
        if current_dir_offset > 0:
            current_dir_dc = "_data-_base"
        kickname_dc=0
        if kickname_offset > 0:
            kickname_dc = "_kickname-_base"
        asm_info_string = self.__asm_string(info_string).replace("*THEDATE*",self.__DATE_REPL)
        output_asm_lines = (self.__HEADER % (self.__VERSION_NUMBER,slave_basename,SLAVE_FUTURE_VERSION,slave_version,flags_str,basemem_size,exec_install,current_dir_dc,key_debug,
        key_exit,expmem_size,kickname_dc,kick_size,kick_crc,current_dir_string,game_name,copyright_string,asm_info_string,kick_string,version_id)).split("\n")

        # this is an executable: use IRA to disassemble it

        ira_path = os.path.join(self.__PROGRAM_DIR,"ira","ira")


        temp_slave = os.path.join(self.__temp_directory,slave_basename)
        with open(temp_slave,"wb") as fsw:
            code_only_slave = b"\x4E\x71"*(entry_offset//2) + self.__slave[entry_offset:-4]
            fsw.write(code_only_slave) # ignore HUNK_END

        self.pass_count = 0
        self.last_pass = False

        while True:

            self.pass_count += 1
            rc = subprocess.call(ira_path+' -a %s -BINARY "%s"' % (opt020,slave_basename),cwd=self.__temp_directory)

            if rc != 0:
                self.__error("unable to run IRA, check that IRA executable is properly installed in %s" % ira_path)
            temp_asm = os.path.splitext(temp_slave)[0] + ".asm"

            fr=open(temp_asm,"r")
            asm_lines = fr.read().splitlines()
            fr.close()

            data_labels = dict()

            label_found = False
            # restore binary data instead of NOPs
            code_start_index = 0
            first_label_index = 0

            for i,asm_line in enumerate(asm_lines):
                if "\tORG\t" in asm_line:
                    break
                if self.last_pass:
                    output_asm_lines.append(asm_line)

            offset = 0


            start_line = i

            for i in range(start_line+1,len(asm_lines)):
                asm_line = asm_lines[i]
                m = re.search(self.__LABEL_RE,asm_line)
                if m:
                    label_found = True
                    m2 = re.search(self.__OFFSET_RE,asm_lines[i+1])
                    if m2:
                        next_offset = int(m2.group(1),16)
                        data_labels[m.group(1)] = next_offset
                        if next_offset<=0x30:
                            label_found=False   # ignore this label, it is within the slave header

                if label_found:
                    first_label_index=i
                    m = re.search(self.__NOP_OFFSET_RE,asm_line)
                    if m:
                        # found a NOP: get offset
                        offset = int(m.group(1),16)
                        if offset>0x30:         # skip whdload header
                            # replace the NOP by 2 dc.b, the last pass will convert to strings if found
                            for z in [0,1]:
                                dcb = "\tdc.b\t"+self.__get_byte_as_hex_string(offset+z)+"\t;%x" % (offset+z)
                                if z==0:
                                    asm_line = dcb
                                if self.last_pass:
                                    output_asm_lines.append(dcb)
                        elif self.last_pass:
                            output_asm_lines.append(asm_line)
                    elif self.last_pass:
                        output_asm_lines.append(asm_line)
                m = re.search(self.__OFFSET_RE,asm_line)
                if m:
                    offset = int(m.group(1),16)
                    if offset==entry_offset-2:  # just the line before entry
                        code_start_index = i+1
                        break

            if self.last_pass:
                output_asm_lines.append("start:")

            # rest_start_index: index of the asm file where the interesting part begins
            if first_label_index>0:
                rest_start_index = first_label_index
            else:
                rest_start_index = code_start_index

            code_lines = asm_lines[code_start_index:]

            self.__offset_keys = []
            # build the dict offset => code/data lines
            slave_len = len(self.__slave)
            self.__code_table = [self.Instruction(MRK_HEADER) for i in range(0,0x30)] + [self.Instruction(MRK_DATA)for i in range(0,(entry_offset-0x30))] + [self.Instruction(MRK_NONE) for i in range(slave_len-entry_offset)]
            for i,asm_line in enumerate(code_lines):
                m2 = re.search(self.__OFFSET_RE,asm_line)
                if m2:
                    k = int(m2.group(1),16)
                    self.__offset_keys.append(k)
                    m3 = re.match(self.__DCW_LINE_RE,asm_line)
                    if m3:
                        # split DC.W into 2 DC.B
                        self.__offset_keys.append(k+1)
                        v = int(m3.group(1),16)
                        self.__code_table[k].line = self.__DCB_FMT % (v>>8,k)
                        self.__code_table[k+1].line = self.__DCB_FMT % (v&0xFF,k+1)
                        # if we encounter instruction trapped between 2 DC, convert it to DCs
                        if i<len(code_lines)-2 and re.match(self.__DCW_LINE_RE,code_lines[i+2]):
                            nextline = code_lines[i+1]
                            m4 = re.match(self.__ASM_LINE_RE,nextline)
                            if m4 and not m4.group(1).startswith("DC"):
                                # instruction found
                                m5 = re.search(self.__OFFSET_RE,nextline)
                                k = int(m5.group(1),16)
                                # spurious instruction
                                # get hex value instead in the comments
                                hvs = nextline.split(":")[1].strip()
                                hv = int(hvs,16)
                                if len(hvs)==4:
                                    new_nextline = "\tDC.W\t$%x\t;%x" % (hv,k)
                                    code_lines[i+1] = new_nextline
                                elif len(hvs)==8:
                                    new_nextline = "\tDC.L\t$%x\t;%x" % (hv,k)
                                    code_lines[i+1] = new_nextline

                                #print nextline, new_nextline
                    else:
                        self.__code_table[k].line = asm_line



            # build the list of labels & their offset
            self.__code_labels = dict()
            for i,asm_line in enumerate(code_lines):
                m = re.search(self.__LABEL_RE,asm_line)
                if m:
                    label_found = True
                    m2 = re.search(self.__OFFSET_RE,code_lines[i+1])
                    if m2:
                        next_offset = int(m2.group(1),16)
                        label = m.group(1)
                        self.__code_labels[label] = next_offset
                        self.__code_table[next_offset].label = label

            # identify which zones are code by following branches and breaking on RTS/RTE

            self.__mark_code(entry_offset)

            address_register_values = [True]+([False]*7)    # A0 contains RESLOAD

            detect_patchlists = False

            # find resload, correct labels, run the code and simulate register addresses modifications
            # to find the jsr resload_xxx(ay) calls and resource them

            label_replacement_dict = dict()
            for ok in self.__offset_keys:
                instruction = self.__code_table[ok]
                line = instruction.line
                m = self.__LABEL_IN_CODE_RE.search(line)
                # first label is most of the time resload
                if m and not label_replacement_dict:
                    label_replacement_dict[m.group(1)] = "_resload"

                if label_replacement_dict:
                    # replace label declarations (resload)
                    if instruction.label in label_replacement_dict:
                        instruction.label = label_replacement_dict[instruction.label]

                    if m:
                        current_label = m.group(1)
                        if current_label in data_labels:
                            # data label offset: compute functional name
                            label_offset = data_labels[current_label]
                            functional_name = self.__HEADER_OFFSET_DICT.get(label_offset,None)
                            if functional_name != None:
                                label_replacement_dict[current_label] = functional_name

                        if current_label in label_replacement_dict:
                            line = line.replace(current_label,label_replacement_dict[current_label])
                            instruction.line = line

                    m = self.__MOVE_RESLOAD_AX_RE.search(line)
                    if m:
                        regi = int(m.group(1))
                        address_register_values[regi]=True
                    else:
                        m = self.__MODIFY_AX_RE.match(line)
                        if m:
                            # register is modified by something other than resload: trash it
                            # unless it is a register transfer from a register containing resload

                            regi = int(m.group(2))
                            source = m.group(1)
                            if source[0]=="A" and source[1].isdigit():
                                srcreg=int(source[1])
                                address_register_values[regi]=address_register_values[srcreg]
                            else:
                                address_register_values[regi]=False
                    if "RTS" in line or "RTE" in line:
                        # break sequence (not optimal!)
                        address_register_values = [False]*8
                        if "RTS" in line:
                            # look for abort, ancient way
                            prerts_instruction = self.__code_table[ok-2].line
                            if prerts_instruction and "ADDQ.L\t#4,(A7)" in prerts_instruction:
                                # pop stack + RTS: could be an Abort call
                                for i in range(ok,ok-7,-1):
                                    if self.__code_table[i].line and "MOVE.L\t_resload(PC),-(A7)" in self.__code_table[i].line:
                                        # we are now sure that this is an abort sequence. Convert all PEAs
                                        # above to abort codes
                                        self.__decode_abort_2(i-1,i-25)

                    else:
                        m = self.__J_OFFSET_RE_1.search(line)
                        if m==None:
                            m = self.__J_OFFSET_RE_2.search(line)
                        if m:
                            # JSR/JMP with register

                            offset_as_string = m.group(2)

                            if offset_as_string[0]=='-':
                                # cannot be resload, ignore
                                pass
                            else:
                                if offset_as_string[0]=='$':
                                    offset = int(offset_as_string[1:],16)
                                if offset_as_string[0]=='(':
                                    # 68020-style
                                    if offset_as_string[1]=='$':
                                        offset = int(offset_as_string[2:],16)
                                    else:
                                        offset = int(offset_as_string[1:])
                                else:
                                    offset = int(offset_as_string)
                                regi = int(m.group(3))
                                if address_register_values[regi]:
                                    # resload call
                                    funcname = self.__resload_offset_dict.get(offset,"unknown_%d" % offset)
                                    if funcname in ["Patch","PatchSeg"]:
                                        detect_patchlists = True
                                    instruction.line = "\t%s\tresload_%s(A%d)\t;%x (offset=%x)" % (m.group(1),funcname,regi,ok,offset)
                                    # special case of some functions: resource above call
                                    if funcname=="Abort":
                                        self.__decode_abort(ok-4,ok-12)

            # now, if there are some Patch calls, scan for patchlists
            if detect_patchlists:
                pl_data = dict()


                for label,offset in sorted(self.__code_labels.items()):
                    pl_start_offset = 0
                    first_short = self.__get_byte(offset)
                    # heuristic to detect patchlists. Can be tricky, so we filter out trivial cases
                    # that can make the decoder crash: 0,0x80,0x40: it's the patch specs
                    # longword=0: cannot be part of a patchlist
                    # short unmarked zone: cannot be part of a patchlist (ex: dc.w 1)
                    if first_short in [0x00,0x80,0x40] and self.__get_be_long(offset)!=0:
                            # unmark start of patchlist which could be just after some non RTS instruction
                            # and be "contaminated"
                            # this works but we have to know the size of the patchlist, so it really doesn't...
                            #self.__mark_zone(offset,4,MRK_NONE)

                        if not self.__is_unmarked(offset,4):
                            self.__warn("Patchlist offset {:x} is already marked, code leaking into patchlist?".format(offset))
                        else:
                            # possibly a patchlist, extra check: check if the label is loaded in A0 at some point
                            rl = re.compile("LEA.*{}.*,A0".format(label))

                            for ok in self.__offset_keys:
                                instruction = self.__code_table[ok]
                                if re.search(rl,instruction.line):
                                    break
                            else:
                                # never loaded in A0
                                continue
                            print("possible patchlist: {}".format(label))
                            self.__pl_offset = offset
                            self.__base_label = offset
                            pl_data[self.__pl_offset] = "PL_START"
                            pl_start_offset = self.__pl_offset

                            while self.__code_table[self.__pl_offset].kind == MRK_NONE:
                                self.__code_table[self.__pl_offset].kind = MRK_PATCHLIST
                                self.__code_table[self.__pl_offset+1].kind = MRK_PATCHLIST
                                cmd = self.__get_be_short(self.__pl_offset)
                                print("{} SHORT {:x} {:x}".format(label,cmd,self.__pl_offset))
                                if cmd==0:
                                    pl_data[self.__pl_offset] = "PL_END"
                                    break   # end of patchlist
                                self.__pl_offset += 2
                                self.__short_param = cmd & 0x8000

                                cmd_table = cmd & 0xFFF

                                valid = True
                                # call function to decode
                                if cmd_table>len(self.__PATCH_JUMPTABLE):
                                    # illegal command: maybe it was not really a patchlist!
                                    print("{}: illegal patchlist, invalid cmd_table {:x}".format(label,cmd_table))
                                    print("PL_DATA:\n\t","\n\t".join(x[1] for x in sorted(pl_data.items())))
                                    valid = False
                                else:
                                    try:
                                        current_offset = self.__pl_offset
                                        args = self.__PATCH_JUMPTABLE[cmd_table](self)
                                        if args==None:
                                            raise Exception("Unsupported patch command %x, %s" % (cmd_table,str(self.__PATCH_JUMPTABLE[cmd_table])))
                                        pline = "%s\t"%args[0]
                                        if len(args)>1:
                                            pline += self.__decode_patch_arg(args[1])

                                        if len(args)>2:
                                            nargs = [self.__decode_patch_arg(a) for a in args[2:]]
                                            pline += ","+",".join(nargs)
                                        pl_data[current_offset] = pline  #          ; cmd_table "+str(cmd_table) + ("%x"%offset) + " "+ label
                                        for i in range(current_offset,self.__pl_saved_offset):
                                            self.__code_table[i].kind = MRK_PATCHLIST
                                        # special case: PL_DATA
                                        if self.__PATCH_JUMPTABLE[cmd_table]==self.__p_DATA:
                                            pass

                                    except WrongPatchArgException:
                                        # illegal arg, maybe it was not really a patchlist
                                        valid = False
                                if not valid:
                                    print("{}: illegal patchlist, rolling back".format(label))
                                    print("PL_DATA:\n\t","\n\t".join(x[1] for x in sorted(pl_data.items())))
                                    # rollback!!!
                                    for i in range(self.__base_label,self.__pl_saved_offset):
                                        self.__code_table[i].kind = MRK_DATA
                                    if pl_start_offset in pl_data:
                                        pl_data.pop(pl_start_offset)  # also remove PL_START
                                    break

            if self.last_pass:
                # no more patch lists to fix
                break

            code_only_slave_list = list(code_only_slave)

            # for next pass, change temp slave so patchlists don't confuse disassembly
            # (we often miss the start of the routine after the patchlist)
            for offset,s in enumerate(self.__code_table):
                if s.kind == MRK_PATCHLIST:
                    code_only_slave_list[offset] = [0x4A,0xFC][offset%2]

            new_code_only_slave = bytes(code_only_slave_list)

            if new_code_only_slave == code_only_slave:
                # no more fixes to perform
                self.last_pass = True
##            else:
##                for i,(a,b) in enumerate(zip(code_only_slave,new_code_only_slave)):
##                    if a!=b:
##                        print("pass {}: old/new diff {:x} vs {:x} at offset ${:x}".format(self.pass_count,a,b,i))

            with open(temp_slave,"wb") as fsw:
                fsw.write(new_code_only_slave)

            code_only_slave = new_code_only_slave

        code_lines = []
        for offset,instruction in enumerate(self.__code_table):
            if instruction.label != None:
                code_lines.append(instruction.label+":")
            if instruction.kind == MRK_PATCHLIST:
                if offset in pl_data:
                    code_lines.append("\t"+pl_data[offset])
            else:
                if instruction.line != None:
                    code_lines.append(instruction.line)

        i = 0

        # insert header asm lines
        code_lines = output_asm_lines+code_lines

        min_len = 5
        dcb_re = re.compile("\tDC.B\t\$([0-9A-F]+)",re.IGNORECASE)
        # last pass: find ASCII in dc.b follow ups
        while i<len(code_lines)-min_len:
            start_index = i
            s=""
            # find the longest DC.B list
            while True:
                if i>len(code_lines)-min_len:
                    break
                line = code_lines[i]
                i+=1

                m = dcb_re.match(line)
                if m:
                    v = int(m.group(1),16)
                    if v>31 and v<128:
                        # ascii
                        s+=chr(v)
                    elif v==0:
                        break
                else:
                    break
            if len(s)>=min_len:
                # found a string: replace all DC.Bs by the string declaration
                code_lines = code_lines[:start_index]+["\tDC.B\t'%s',0"%s]+code_lines[i:]
                i = start_index+1


        import io
        fw = io.StringIO()

        for l in code_lines:
            l = l.replace("ORI.B\t#$00,D0","dc.l\t0")  # todo: ORI.B	#$00,Dx => 000x0000
            l = l.replace("'',0","0")
            if l:
                fw.write(l)
                lstrip = l.strip()
                for i in ["RTS","RTE","JMP","PL_END"]:
                    if lstrip.startswith(i):
                        fw.write("\n")
                        break
                fw.write("\n")

        with open(self.__current_output_file,"wb") as f:
            f.write(fw.getvalue().replace("\r","").encode("ascii"))


    def __get_patch_long(self):
        rval = self.__get_be_long(self.__pl_offset)
        self.__pl_offset += 4
        self.__pl_saved_offset = self.__pl_offset
        return rval
    def __get_patch_word(self):
        rval = self.__get_be_short(self.__pl_offset)
        self.__pl_offset += 2
        self.__pl_saved_offset = self.__pl_offset
        return rval
    def __get_patch_byte(self):
        rval = self.__get_byte(self.__pl_offset)
        self.__pl_offset += 1
        self.__pl_saved_offset = self.__pl_offset
        return rval

    def __get_patch_offset(self):
        if self.__short_param:
            rval = self.__get_be_short(self.__pl_offset)
            self.__pl_offset += 2
        else:
            rval = self.__get_be_long(self.__pl_offset)
            self.__pl_offset += 4
        self.__pl_saved_offset = self.__pl_offset
        return rval

    def __get_slave_address(self):
        rval = self.__get_be_short(self.__pl_offset,True)
        self.__pl_offset += 2

        rval += self.__base_label
        self.__pl_saved_offset = self.__pl_offset
        return rval

    def __p_R(self):
        return ["PL_R",self.__get_patch_offset()]

    def __p_PXXX(self,op):
        rval = [op,self.__get_patch_offset()]
        sladdr = self.__get_slave_address()
        # mark the zone as code
        if sladdr%2:
            raise WrongPatchArgException()
        self.__mark_code(sladdr)
        return rval + [[sladdr,True]]
    def __p_PS(self):
        return self.__p_PXXX("PL_PS")
    def __p_P(self):
        return self.__p_PXXX("PL_P")
    def __p_S(self):
        rval = ["PL_S",self.__get_patch_offset()]
        rval += [[self.__get_patch_word()+2,False]]
        return rval
    def __p_I(self):  # 5 set ILLEGAL
        return ["PL_I",self.__get_patch_offset()]
    def __p_B(self):  # 6 write byte to specified address
        rval = ["PL_B",self.__get_patch_offset()]
        rval += [[self.__get_patch_byte(),False]]
        return rval

    def __p_W(self):  # 7 write word to specified address
        patch_offset = self.__get_patch_offset()
        patch_word = self.__get_patch_word()
        if patch_word == 0x4E71:
            rval = ["PL_NOP",patch_offset,[2,False]]
        elif patch_word == 0x4E75:
            rval = ["PL_R",patch_offset]
        else:
            rval = ["PL_W",patch_offset]
            rval += [[patch_word,False]]
        return rval

    def __p_L(self):  # 8 write long to specified address
        patch_offset = self.__get_patch_offset()
        patch_long = self.__get_patch_long()
        if patch_long == 0x4E714E71:
            rval = ["PL_NOP",patch_offset,[4,False]]
        else:
            rval = ["PL_L",patch_offset,[patch_long,False]]
        return rval
# version 11
    def __p_WA(self):  # 9 (A) write address which is calculated as
        pass
					#base + arg to specified address
# version 14
    # when 2 methods are needed when composing the return array,
    # we do it one by one, because there's an edge effect (pl_offset gets modified)
    # and it is dependent on the evaluation order. Now it would work, but we never know...
    def __p_PA(self):  # $A write address given by argument to
        rval = ["PL_PA",self.__get_patch_offset()]
        rval += [[self.__get_slave_address(),True]]
        return rval
					#specified address
    def __p_NOP(self):  # $B fill given area with NOP instructions
        rval = ["PL_NOP",self.__get_patch_offset()]
        rval += [[self.__get_patch_word(),False]]
        return rval
# version 15
    def __p_CNB(self):  # $C (C) clear n bytes
        return ["PL_C",self.__get_patch_offset(),self.__get_patch_word()]
    def __p_CB(self):  # $D clear one byte
        return ["PL_CB",self.__get_patch_offset()]
    def __p_CW(self):  # $E clear one word
        return ["PL_CW",self.__get_patch_offset()]
    def __p_CL(self):  # $F clear one long
        return ["PL_CL",self.__get_patch_offset()]
# version 16
    def __p_PSS(self):  # $11 set JSR + NOP..
        return __p_PXXX("PSS")

    def __p_NEXT(self):  #continue with another patch list
        self.__pl_offset += 2       # skip 0000
        self.__pl_offset = self.__get_slave_address()
        self.__base_label = self.__pl_offset
        return ["PL_NEXT",[self.__pl_offset,True]]

    def __p_AB(self):  #add byte to specified address
        rval = ["PL_AB",self.__get_patch_offset()]
        rval += [[self.__get_patch_byte(),False]]
        return rval
    def __p_AW(self):  #add word to specified address
        rval = ["PL_AW",self.__get_patch_offset()]
        rval += [[self.__get_patch_word(),False]]
        return rval
    def __p_AL(self):  #add long to specified address
        rval = ["PL_AL",self.__get_patch_offset()]
        rval += [[self.__get_patch_long(),False]]
        return rval
    def __p_DATA(self):  #write n data bytes to specified address
# version 16.5
        rval = ["PL_DATA",self.__get_patch_offset(),self.__get_patch_word()]
        self.__pl_offset += rval[-1]  # TODO print data
        return rval
    def __p_ORB(self):  #or byte to specified address
        rval = ["PL_ORB",self.__get_patch_offset()]
        rval += [[self.__get_patch_byte(),False]]
        return rval
    def __p_ORW(self):  #or word to specified address
        rval = ["PL_ORW",self.__get_patch_offset()]
        rval += [[self.__get_patch_word(),False]]
        return rval
    def __p_ORL(self):  #or long to specified address
        rval = ["PL_ORL",self.__get_patch_offset()]
        rval += [[self.__get_patch_long(),False]]
        return rval
# version 16.6
    def __p_GA(self):  # (GA) get specified address and store it in the slave
        raise Exception("GA")
        pass
# version 16.9
    def __p_FRZ(self):  #call freezer
        raise Exception("FREEZER")
        pass
    def __p_VBELL(self):  #show visual bell
        raise Exception("VISUALBELL")
        pass
# version 17.2
    def __p_IFBW(self):  #condition if ButtonWait/S
        return ["P_IFBW"]
    def __p_IFC1(self):  #condition if Custom1/N
        return ["P_IFC1"]
    def __p_IFC2(self):  #condition if Custom2/N
        return ["P_IFC2"]
    def __p_IFC3(self):  #condition if Custom3/N
        return ["P_IFC3"]
    def __p_IFC4(self):  #condition if Custom4/N
        return ["P_IFC4"]
    def __p_IFC5(self):  #condition if Custom5/N
        return ["P_IFC5"]
    def __p_IFC1X(self):  #condition if bit of Custom1/N
        return ["P_IFC1X"]
    def __p_IFC2X(self):  #condition if bit of Custom2/N
        return ["P_IFC2X"]
    def __p_IFC3X(self):  #condition if bit of Custom3/N
        return ["P_IFC3X"]
    def __p_IFC4X(self):  #condition if bit of Custom4/N
        return ["P_IFC4X"]
    def __p_IFC5X(self):  #condition if bit of Custom5/N
        return ["P_IFC5X"]
    def __p_ELSE(self):  #condition alternative
        return ["P_ELSE"]
    def __p_ENDIF(self):		#end of condition block
        return ["P_ENDIF"]

    __PATCH_JUMPTABLE = [None,  # 0
	__p_R		,  # 1
	__p_P			,  # 2 set JMP
	__p_PS		,  # 3 set JSR
	__p_S			,  # 4 set BRA (skip)
	__p_I			,  # 5 set ILLEGAL
	__p_B			,  # 6 write byte to specified address
	__p_W			,  # 7 write word to specified address
	__p_L			,  # 8 write long to specified address
# version 11
	__p_WA			,  # 9 (A) write address which is calculated as
					#base + arg to specified address
# version 14
	__p_PA		,  # $A write address given by argument to
					#specified address
	__p_NOP		,  # $B fill given area with NOP instructions
# version 15
	__p_CNB			,  # $C (C) clear n bytes
	__p_CB		,  # $D clear one byte
	__p_CW		,  # $E clear one word
	__p_CL		,  # $F clear one long
# version 16
	__p_PSS		,  # $11 set JSR + NOP..
	__p_NEXT		,  #continue with another patch list
	__p_AB		,  #add byte to specified address
	__p_AW		,  #add word to specified address
	__p_AL		,  #add long to specified address
	__p_DATA		,  #write n data bytes to specified address
# version 16.5
	__p_ORB		,  #or byte to specified address
	__p_ORW		,  #or word to specified address
	__p_ORL		,  #or long to specified address
# version 16.6
	__p_GA		,  # (GA) get specified address and store it in the slave
# version 16.9
	__p_FRZ		,  #call freezer
	__p_VBELL		,  #show visual bell
# version 17.2
	__p_IFBW		,  #condition if ButtonWait/S
	__p_IFC1		,  #condition if Custom1/N
	__p_IFC2		,  #condition if Custom2/N
	__p_IFC3		,  #condition if Custom3/N
	__p_IFC4		,  #condition if Custom4/N
	__p_IFC5		,  #condition if Custom5/N
	__p_IFC1X		,  #condition if bit of Custom1/N
	__p_IFC2X		,  #condition if bit of Custom2/N
	__p_IFC3X		,  #condition if bit of Custom3/N
	__p_IFC4X		,  #condition if bit of Custom4/N
	__p_IFC5X		,  #condition if bit of Custom5/N
	__p_ELSE		,  #condition alternative
	__p_ENDIF		#end of condition block
]

    def __doit(self):
        self.__create_temp_directory()
        # main processing here
        self.__resload_offset_dict = dict()
        self.__tdreason_dict = dict()
        i = 0
        for l in self.__RESLOAD_FUNCTIONS:
            m = re.match(self.__RESLOAD_FUNCTION_RE,l)
            if m:
                name = m.group(1)
                self.__resload_offset_dict[i] = name
                i+=4

        for l in self.__ABORT_CODES:
            m = re.match(self.__ABORT_REASON_RE,l)
            if m:
                name = m.group(1)
                self.__tdreason_dict[int(m.group(2))] = name


        for f in self.__input_files:
            self.__current_slave_file = f
            self.__current_output_file = os.path.splitext(f)[0]+".asm"
            self.__message("Processing %s" % f)
            self.__process_file()

if __name__ == '__main__':
    """
        Description :
            Main application body
    """


    o = WHDSlaveResourcer()
    o.init_from_sys_args(debug_mode = True)
    #o.init("output_file")
