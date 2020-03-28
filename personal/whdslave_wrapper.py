#!/usr/bin/python

# coded by JOTD (C) 2018

import os,sys,re,subprocess
import getopt,traceback
import glob,shutil


try:
    unicode
    ord2 = ord
except NameError:
    ord2 = lambda x:x

class WHDSlaveWrapper:
    __VERSION_NUMBER = "0.9"
    __MODULE_FILE = __file__
    __PROGRAM_NAME = os.path.basename(__MODULE_FILE)
    __PROGRAM_DIR = os.path.abspath(os.path.dirname(__MODULE_FILE))

    def __init__(self):
        self.__logfile = ""
        self.__current_slave_file = "No slave"
        # init members with default values

        self.__input_files= []

    def init_from_custom_args(self,args):
        self.__do_init(args)

    def init_from_sys_args(self,debug_mode = True):
        """ standalone mode """

        try:
            self.__do_init(sys.argv[1:])
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

    def __do_init(self,args):
        self.__opts = None
        self.__args = None
        #count_usage.count_usage(self.__PROGRAM_NAME,1)
        self.__parse_args(args)
        self.__doit()

    def __purge_log(self):
        if self.__logfile != "":
            try:
                os.remove(self.__logfile)
            except:
                pass
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

    def __message(self,msg):
        msg = self.__PROGRAM_NAME+(": %s" % msg)+os.linesep
        sys.stderr.write(msg)
        if self.__logfile != "":
            f = open(self.__logfile,"a")
            f.write(msg)
            f.close()

    def __error(self,msg):
        raise Exception("Error: %s (%s)" % (msg,self.__current_slave_file))

    def __warn(self,msg):
        self.__message("Warning: "+msg)

    def __parse_args(self,args):
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

        self.__opts, self.__args = getopt.getopt(args, sostr,longopts_eq)


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

    __RESLOAD_FUNCTION_RE = re.compile(r"^\s*\w+\s+resload_(\w+)")
    __WDATE_RE = re.compile(r"\(\d\d\-[a-z]+\-\d\d\s+\d\d:\d\d:\d\d\)")
    __DATE_REPL = "'\n\tINCBIN\tT:date\n\tdc.b\t'"

    __SPY_CONFIG = {"LoadFile": [{"a0c":"filename","a1p":"dest"},{"d0":"filesize","d1":"errorcode"}],
                    "GetFileSize" : [{"a0c":"filename"},{"d0":"filesize"}],
                    "LoadFileOffset" :[{"d0":"size","d1":"offset","a0c":"filename","a1p":"dest"},{"d0":"success","d1":"errorcode"}],
                    "GetCustom":[{"d0":"buflen","d1":"reserved0","a0p":"outbuffer"},{"d0":"success"}],
                    "Examine" : [{"a0c":"filename","a1p":"fileinfoblock"},{"d0":"success","d1":"errorcode"}],
        }
    # decrunch counterparts have the same signature
    __SPY_CONFIG["LoadFileDecrunch"] = __SPY_CONFIG["LoadFile"]
    __SPY_CONFIG["GetFileSizeDec"] = __SPY_CONFIG["GetFileSize"]

    __KICKCRCDICT = { 0x970C : "KICKCRC600",0x9FF5 : "KICKCRC1200",0x75D3 : "KICKCRC4000"}

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

    __HEADER = """; whd slave wrapper
; a program written by JOTD in 2018
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

LOG_BUFFER_SIZE = $200000
%s

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
	dc.l	$%x+LOG_BUFFER_SIZE   	; ws_expmem
	dc.w	_name-_base				; ws_name
	dc.w	_copy-_base				; ws_copy
	dc.w	_info-_base				; ws_info
    dc.w    %s     ; kickstart name
    dc.l    $%x         ; kicksize
    dc.w    $%x         ; kickcrc
    dc.w    _config-_base         ; config

;---

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
_kickname
%s
;--- version id

    dc.b	%s
_config:
    dc.b    %s0
    even
start:
"""

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


    def __get_string(self,offset,length):
        return self.__slave[offset:offset+length]
    def __get_c_string(self,offset):
        i = offset
        while True:
            if ord2(self.__slave[i])==0:
                break
            i+=1
        return self.__slave[offset:i].replace(b"\xff",b"\n").decode("ascii",errors="ignore")

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
        expmem_size = self.__get_be_long(32)
        header_size = 36

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
            header_size = 0x2A

        if slave_version>15:
            kickname_offset = self.__get_be_short(0x2A)
            kick_size = self.__get_be_long(0x2C)
            kick_crc = self.__get_be_short(0x30)
            if kickname_offset>0:
                if kick_crc == 0xFFFF:
                    kick_string = []
                    kickcrc_offset = kickname_offset
                    while True:
                        crc = self.__get_be_short(kickcrc_offset)
                        if not crc:
                            break
                        short_ptr = self.__get_be_short(kickcrc_offset+2)
                        sk = self.__get_c_string(short_ptr)
                        kickcrc_offset += 4
                        # multi-kick: kick_string is a list
                        kick_string.append((crc,sk))

                else:
                    kick_string = self.__get_c_string(kickname_offset)
            header_size = 0x32

        config_string = ""
        if slave_version>16:
            config_offset = self.__get_be_short(0x32)
            if config_offset:
                config_string = '"{}",'.format(self.__get_c_string(config_offset))
            header_size = 0x34

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
        if slave_version > 16:
            self.__message("Config string: %s" % config_string)
        current_dir_dc = "0"
        if current_dir_offset > 0:
            current_dir_dc = "_data-_base"
        kickname_dc=0
        if kickname_offset > 0:
            kickname_dc = "_kickname-_base"
        if isinstance(kick_string,list):
            # multikick
            ks = "\n".join("     dc.w     {},.{}-_base".format(self.__KICKCRCDICT.get(crc,"${:x}".format(crc)),name.rpartition(".")[-1]) for crc,name in kick_string)
            ks += "\n    dc.w   0\n"
            ks += "\n".join('.{}     dc.b     "{}",0'.format(name.rpartition(".")[-1],name) for _,name in kick_string)
            kick_string = ks
        else:
            kick_string = "     dc.b    '{}',0".format(kick_string)

        asm_info_string = self.__asm_string(info_string).replace("*THEDATE*",self.__DATE_REPL)
        kickcrc_decls = "".join("{} = ${:x}\n".format(name,crc) for crc,name in sorted(self.__KICKCRCDICT.items()))

        output_asm_lines = (self.__HEADER % (slave_basename,kickcrc_decls,slave_version,slave_version,flags_str,basemem_size,exec_install,current_dir_dc,key_debug,
        key_exit,expmem_size,kickname_dc,kick_size,kick_crc,current_dir_string,game_name,copyright_string,asm_info_string,kick_string,version_id,config_string))


        with open(self.__current_output_file,"w") as f:
            def  write_instr(l):
                f.write("    {}\n".format(l))

            sorted_funcalls = sorted(self.__resload_offset_dict.items())
            sorted_funcalls.pop()
            sorted_funcalls.pop()

            f.write(output_asm_lines)
            f.write(""" ; copy the slave data to the original slave
     lea    _resload(pc),a1
     move.l a0,(a1)
     lea    orig+$20(pc),a1         ; slave base
     move.l _expmem(pc),($20,a1)    ; relocate expansion memory in original whdload struct
     ;;move.l _expmem(pc),$100.W      ; save to $100 just in case, but sometimes lead to a crash!!!
     move.b #$45,(31,a1)            ; change keyexit so pressing ESC calls the non-VBR routine if present, so it calls "Abort"
     ;;; add.l  #LOG_BUFFER_SIZE,($20,a1)   ; but shifted by the log buffer size (expmem is the buffer start)
     move.l a1,-(a7)
     move.w (24,a1),d0
     ext.l  d0
     add.l    d0,(a7)     ; entry offset

     ; now redirect to fake resload
     lea    _fake_resload(pc),a0

    move.l  #$D0D0D0D0,d0
    move.l  #$A1A1A1A1,a1
    rts
_resload:
     dc.l   0
""")
            funcalls = [v for _,v in sorted_funcalls if v not in ["Abort"]]

            for v in funcalls:
                # log whd call name
                string_constants = {}
                f.write("""wrap_{0}:
      movem.l   a3,-(a7)
      lea   {0}_name(pc),a3
      bsr   log_string
""".format(v))
                def log_params(params):
                    write_instr("movem.l   d0,-(a7)")
                    sp = sorted(params.items())
                    for i,(reg,desc) in enumerate(sp):
                        # generate code to write desc & C string
                        string_constants[desc] = desc
                        write_instr("lea  .{}(pc),a3".format(desc))
                        write_instr("bsr  log_string")
                        write_instr("bsr   log_space")
                        write_instr("lea  str_{}(pc),a3".format(reg[0:2]))
                        write_instr("bsr  log_string")
                        write_instr("bsr  log_arrow")
                        if reg[0]=='a':
                            # address reg
                            is_string = reg[-1] == "c"
                            addr_reg = reg[:-1]
                            # now value as string
                            if is_string:
                                write_instr("move.l   {},a3".format(addr_reg))
                                write_instr("bsr  log_string")
                            else:
                                write_instr("move.l   {},d0".format(addr_reg))
                                write_instr("bsr   log_number")
                        else:
                            # data
                            if reg != "d0":
                                write_instr("move.l   {},d0".format(reg))
                            write_instr("bsr   log_number")
                        if i==len(sp)-1:
                            write_instr("bsr   log_parentlf")
                        else:
                            write_instr("bsr   log_comma")

                    write_instr("movem.l   (a7)+,d0")

                # now log parameters if configured
                if v in self.__SPY_CONFIG:
                    params_in,params_out = self.__SPY_CONFIG[v]
                    log_params(params_in)

                # default, not watched
                write_instr("; call orig. function {}".format(v))
                write_instr("move.l    _resload(pc),a3")
                write_instr("jsr       (resload_{0},a3)\n".format(v))
                if v in self.__SPY_CONFIG:
                    write_instr("bsr   log_space")
                    write_instr("bsr   log_space")
                    log_params(params_out)
                write_instr("bsr   log_parentlf")
                write_instr("movem.l   (a7)+,a3")
                write_instr("tst.l     d0")
                write_instr("rts")
                if string_constants:
                    for c in string_constants.items():
                        f.write('.{}:\n    dc.b    "{}",0\n'.format(*c))
                    write_instr("even\n")
            # dump utility functions
            f.write("""wrap_Abort:
     ; now write the memory
     move.l _resload(pc),a3
     lea    .dumpfile(pc),a0
     move.l _expmem(pc),a1
     add.l  #{expmem_size},a1
     move.l current_offset(pc),d0   ; len
     jsr    (resload_SaveFile,a3)
     ; and abort
     jmp       (resload_Abort,a3)
.dumpfile
    dc.b    "__log.txt",0
    even
log_parentlf:
    lea parentlf(pc),a3
    bra  log_string
log_arrow:
    lea arrow(pc),a3
    bra  log_string
log_comma:
    lea comma(pc),a3
    bra  log_string
log_space:
    lea space(pc),a3
    bra  log_string
log_newline:
    lea newline(pc),a3
; < A3: string to log
log_string:
    movem.l   d3/a4/a5,-(a7)
    lea     current_offset(pc),a4
    move.l  (a4),d3
    move.l  _expmem(pc),a5
    add.l   #{expmem_size},a5
.copy
    move.b  (a3)+,(a5,d3.l)
    beq.b   .out
    addq.l  #1,d3
    cmp.l   #LOG_BUFFER_SIZE,d3
    bne.b   .copy
    moveq.l #0,d3
    bra.b   .copy
.out
    ; store current offset
    move.l  d3,(a4)
    movem.l   (a7)+,d3/a4/a5
    rts
current_offset
    dc.l    0
newline:
    dc.b    10,0
comma:
    dc.b    ", ",0
parentlf:
    dc.b    ")",10,0
space:
    dc.b    " ",0
str_d0:
    dc.b    "D0",0
str_d1:
    dc.b    "D1",0
str_d2:
    dc.b    "D2",0
str_a0:
    dc.b    "A0",0
str_a1:
    dc.b    "A1",0
arrow:
    dc.b    " => ",0
    even

; *** Converts a hex number to a ascii string (size 9 $xxxxxxxx)
; in: D0: number
; in: A1: pointer to destination buffer
; out: nothing

log_number:
	movem.l    d0-d4/a3,-(a7)
    lea .digitbuffer(pc),a3
	moveq.l	#7,D4		; 8 digits
	bsr	__HexToString
    lea .digitbuffer(pc),a3
    bsr log_string
	movem.l    (a7)+,d0-d4/a3
	rts
.digitbuffer
    ds.b    10,0
; internal HexToString

__HexToString:
	move.l	#$F0000000,D3
	moveq.l	#4,D2
	move.b	#'$',(A3)+
.loop
	move.l	D0,D1
	and.l	D3,D1
	rol.l	D2,D1
	cmp.b	#9,D1
	bgt	.letter
	add.b	#'0',D1
	move.b	D1,(A3)+
	bra	.loopend
.letter
	add.b	#'A'-10,D1
	move.b	D1,(A3)+
.loopend
	addq.l	#4,D2
	lsr.l	#4,D3
	dbf	D4,.loop
	rts
""".format(expmem_size=expmem_size))
            f.write("_fake_resload\n")
            for _,v in sorted_funcalls:
                f.write("   bra.w    wrap_{}\n".format(v))
            f.write("_fake_resload_end\n")
            for _,v in sorted_funcalls:
                f.write("{0}_name:\n    dc.b  '{0}(',0\n".format(v))
            f.write("    even\norig:\n    incbin    '{}'\n".format(os.path.basename(self.__current_slave_file)))

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

        for f in self.__input_files:
            self.__current_slave_file = f
            self.__current_output_file = os.path.splitext(f)[0]+"_wrappedHD.s"
            self.__message("Processing %s" % f)
            self.__process_file()

if __name__ == '__main__':
    """
        Description :
            Main application body
    """


    o = WHDSlaveWrapper()
    o.init_from_sys_args(debug_mode = True)
    #o.init("output_file")
