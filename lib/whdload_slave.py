import re,os

def get_be_short(s,offset):
    return s[offset]*256+s[offset+1]
def get_byte(s,offset):
    return s[offset]

def get_be_long(s,offset):
    return (get_be_short(s,offset)<<16) + get_be_short(s,offset+2)

def get_c_string(contents,offset):
    i = offset
    while True:
        if contents[i]==0:
            break
        i+=1
    return contents[offset:i].replace(b"\xff",b"\n").decode("latin-1")

def warn(msg):
    print("warning: "+msg)

class WHDLoadSlave:
    def __eq__(self,other):
        return self.raw_bytes == other.raw_bytes
    def __neq__(self,other):
        return self.raw_bytes != other.raw_bytes

    def __init__(self,slave):
        self.slave = slave
        with open(slave,"rb") as f:
            header = f.read(0x20)
            contents = f.read()

        self.game_full_name = None
        self.raw_bytes = contents
        self.error = None

        h = contents[4:12]

        self.valid = False
        if h!=b"WHDLOADS":
            self.error = "{}: not a slave, found {!r} header".format(slave,h)
            return

        self.version_string = ""
        version_string_pos = contents.find(b"$VER:")
        if version_string_pos != -1:
            zero_pos = contents.find(0,version_string_pos)
            self.version_string = contents[version_string_pos:zero_pos].decode("ascii","ignore")

        self.valid = True
        self.slave_version = get_be_short(contents,12)
        flags = get_be_short(contents,14)
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

        self.flags_list = flags_list

        self.slave_info = ""
        self.slave_copyright = ""
        self.basemem_size = get_be_long(contents,16)
        self.exec_install = get_be_long(contents,20)
        self.entry_offset = get_be_short(contents,24)
        self.current_dir_offset = get_be_short(contents,26)
        self.dont_cache = get_be_short(contents,28)
        self.key_debug = get_byte(contents,30)
        self.key_exit = get_byte(contents,31)
        self.expmem_size = get_be_long(contents,32)
        if self.expmem_size>0x800000:
            # probably negative: optional
            self.expmem_size=0

        self.kick_string=""
        self.kick_size=0
        if self.slave_version>15:
            kickname_offset = get_be_short(contents,0x2A)
            if kickname_offset>0:
                self.kick_string = get_c_string(contents,kickname_offset)
            self.kick_size = get_be_long(contents,0x2C)

        if self.slave_version>9:
            slave_name_offset = get_be_short(contents,0x24)
            # remove suspiciously long names or ISO image will be corrupt and crash
            gfnu = get_c_string(contents,slave_name_offset).replace("-->","").replace("<--","")
            gfnu = re.sub(r"[<>\*:/\(\)]"," ",gfnu) # illegal chars
            gfnu = re.sub(r"\s+"," ",gfnu) # double space chars
            gfnu = re.sub(r"^[\-\+]*","",gfnu) # starting with DASH/PLUS
            self.game_full_name = re.sub(r"(........)[:\-/].*",r"\1",gfnu).strip()
            # workaround for Galahad strange way of naming slaves: S W I T C H B L A D E
            if re.match(r"\s+",self.game_full_name[1::2]):
                self.game_full_name = self.game_full_name[::2]
            # problem with ISOFS when filename too long (> 30 ?)
            while len(self.game_full_name)>24: # ".start" suffix counts
                prevlen = len(self.game_full_name)
                # trucate last word
                z = self.game_full_name.rfind(" ")
                self.game_full_name=self.game_full_name[:z]
                if len(self.game_full_name)==prevlen: # cannot truncate
                    warn("Cannot truncate %s properly below 24 chars" % self.game_full_name)
                    break
            slave_copy_offset = get_be_short(contents,0x26)
            self.slave_copyright = get_c_string(contents,slave_copy_offset)
            slave_info_offset = get_be_short(contents,0x28)
            self.slave_info = get_c_string(contents,slave_info_offset)
        else:
            self.game_full_name = os.path.splitext(os.path.basename(slave))[0]


