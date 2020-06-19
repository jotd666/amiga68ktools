import struct,os

type_dict = {"UINT16BE":("H",2),"INT16BE":("h",2),"UINT8":("B",1)}

def ilbm_info(filename):
    filesize = os.path.getsize(filename)
    with open(filename,"rb") as f:
        def get_int():
            return struct.unpack(">I",f.read(4))[0]
        def get_fourcc():
            return f.read(4)

        form = get_fourcc()
        if form != b"FORM":
            raise Exception("Not an IFF file")
        size = get_int()
        if size+8 != filesize:
            raise Exception("File & main chunk size don't match {}+8 != {}".format(size,filesize))
        form = f.read(4)
        if form != b"ILBM":
            raise Exception("Not an ILBM file")

        d = {}
        while len(d)<3:
            form = get_fourcc()
            if not form:
                break

            if form not in [b"BMHD",b"CMAP",b"BODY"]:
                raise Exception("expected chunk name at offset ${:x}".format(f.tell()-4))
            chunk_size = get_int()

            if form==b"BMHD":
                header = {}
                for t,k in (x.split() for x in """UINT16BE	width
    UINT16BE	height
    INT16BE	xOrigin
    INT16BE	yOrigin
    UINT8	numPlanes
    UINT8	mask
    UINT8	compression
    UINT8	pad1
    UINT16BE	transClr
    UINT8	xAspect
    UINT8	yAspect
    INT16BE	pageWidth
    INT16BE	pageHeight""".splitlines()):
                    fmt,sz = type_dict[t]
                    header[k] = struct.unpack(">"+fmt,f.read(sz))[0]

                d[form] = header
            else:
                d[form] = f.read(chunk_size)

    print(d[b"BMHD"])
    print(len(d[b"CMAP"]))

if __name__ == "__main__":
    ilbm_info(r"K:\jff\data\python\compilation_maker\data\images\A\AddamsFamily\igame.iff")
    ilbm_info(r"K:\jff\data\python\compilation_maker\data\images\A\Alien3\igame.iff")