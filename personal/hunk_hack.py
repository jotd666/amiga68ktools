import struct

hunk_dict = {0x3F3:"header",0x3E9:"code",0x3EA:"data",0x3F2:"end",0x3EC:"reloc32",0x3EB:"bss"}
def read_long(f):

    return struct.unpack(">I",f.read(4))[0]

def decode(input_file):
    with open(input_file,"rb") as f:

        header = read_long(f)
        if header != 0x3F3:
            raise Exception("wrong header")
        strings = read_long(f)
        nb_hunks = read_long(f)
        start_hunk = read_long(f)
        end_hunk = read_long(f)
        hunk_sizes = []
        for _ in range(nb_hunks):
            value = read_long(f)
            # flags, value
            hunk_sizes.append(((value & 0xC0000000) >> 29,value & 0x3FFFFFFF))

        print("nb_hunks = {}, start = {}, end = {}".format(nb_hunks,start_hunk,end_hunk))

        i = 1
        for _ in range(nb_hunks):
            # now the hunks (no need to remind the memory constraints)
            hunk_type = (read_long(f) & 0x3FFFFFFF)
            if hunk_type == 0x3F2:
                continue
            hunk_size = read_long(f)  # should be the same as the one previously read
            print("Hunk #{}, type ${:x} ({}), size ${:x}".format(i,hunk_type,hunk_dict[hunk_type],hunk_size))
            i+=1
            data = f.read(hunk_size*4)
            hunk_next = read_long(f)
            if hunk_next == 0x3F2:
                continue
            if hunk_next == 0x3EC:
                # reloc
                hunk_reloc_start = f.tell()
                while True:
                    nb_relocs = read_long(f)
                    if nb_relocs==0:
                        break
                    target_hunk = read_long(f)
                    reloc_data = [read_long(f) for _ in range(nb_relocs)]
                hunk_reloc_end = f.tell()
                hunk_size = hunk_reloc_end - hunk_reloc_start
                print("Hunk #{}, type ${:x} ({}), size ${:x}".format(i,hunk_next,hunk_dict[hunk_next],hunk_size))
                i+=1
            #print(hex(hunk_end),hex(f.tell()))

decode(r"C:\DATA\jff\AmigaHD\PROJETS\HDInstall\ARetoucher\MarbleMadnessHDDev\data\PrcSnd")

