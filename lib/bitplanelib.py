import PIL.Image,math,struct

def bitplanes_colors_used(contents,nb_planes,width,height):
    """
    analyzes a ripped planar image
    height : -1: autocompute from contents size & width & nb planes
    returns a set of palette indexes
    """
    if height < 0:
        height = (len(contents)//(width*nb_planes))*8


    plane_size = (width//8)*height
    rval = set()

    for y in range(height):
        for x in range(0,width,8):
            offset = (y*width + x)//8
            for i in range(8):
                value = 0
                shift = (1<<(7-i))

                for p in range(nb_planes):
                    if (shift & contents[p*plane_size + offset]):
                        value |= 1<<p

                rval.add(value)
    return rval

def bitplanes_raw2image(contents,nb_planes,width,height,output_filename,palette):
    """
    converts a ripped planar image + palette to png
    height : -1: autocompute from contents size & width & nb planes
    """
    if height < 0:
        height = (len(contents)//(width*nb_planes))*8

    img = PIL.Image.new('RGB', (width,height))


    plane_size = (width//8)*height

    for y in range(height):
        for x in range(0,width,8):
            offset = (y*width + x)//8
            for i in range(8):
                value = 0
                shift = (1<<(7-i))

                for p in range(nb_planes):
                    if (shift & contents[p*plane_size + offset]):
                        value |= 1<<p

                img.putpixel((x+i,y),palette[value])

    if output_filename:
        img.save(output_filename)
    return img

def bitplanes_raw2planarimage(contents,nb_planes,width,height,output_filename=None):

    img = PIL.Image.new('RGB', (width*nb_planes,height))

    biter = iter(contents)

    for plane in range(nb_planes):
        start_x = plane * width
        start_y = 0
        for y in range(height):
            for x in range(0,width,8):
                eight_pixs = next(biter)
                for i in range(8):
                    if ((1<<(7-i)) & eight_pixs):
                        img.putpixel((start_x+x+i,start_y+y),(0xFF,0xFF,0xFF))

    if output_filename:
        img.save(output_filename)
    return img

def bitplanes_planarimage2raw(input_image,nb_planes,output_filename=None):
    """ converts a png/whatever to a raw planar image, 1 plane
    (if not black then it's a pixel)
    if output_filename is not None, then save as file. Else just return created data
    """
    if isinstance(input_image,str):
        img = PIL.Image.open(input_image)
    else:
        img = input_image

    full_width,height = img.size
    plane_width = full_width // nb_planes
    out = []

    for plane in range(nb_planes):
        start_x = plane * plane_width
        start_y = 0
        for y in range(height):
            for x in range(start_x,start_x+plane_width,8):
                eight_pixs = 0
                for i in range(8):
                    p = img.getpixel((x+i,start_y+y))
                    if p[:3] != (0,0,0):
                        eight_pixs |= (1<<(7-i))
                out.append(eight_pixs)
    out = bytes(out)
    if output_filename:
        with open(output_filename,"wb") as f:
            f.write(out)
    return out


def palette_dcw2palette(text):
    """ converts a dc.w line list ($xx,$yy...) to a palette
    """
    rgblist = []
    for line in text.splitlines():
        line = line.lower()
        toks = line.split()
        if toks and toks[0] == "dc.w":
            rgblist.extend(int(x,16) for x in toks[1].strip("$").split(",$"))

    rval = [(((v & (0xF00))>>4),((v & (0xF0))),((v & (0xF))<<4)) for v in rgblist]
    return rval

def palette_toehb(palette):
    rval = palette.copy()
    for r,g,b in palette:
        rval.append(((r//2)&0xF0,(g//2)&0xF0,(b//2)&0xF0))
    return rval

def palette_regdump2palette(text):
    """ converts a winuae custom register dump to a palette
    """
    toks = iter(text.split())
    rval = dict()
    try:
        while True:
            v = next(toks)
            if v.startswith("COLOR"):
                index = int(v[-2:])
                v = int(next(toks),16)
                rval[index] = ((v & (0xF00))>>4),((v & (0xF0))),((v & (0xF))<<4)

    except StopIteration:
        pass
    return [item for k,item in sorted(rval.items())]

def __palette_dump(palette,f,as_copperlist,as_binary,low_nibble):
    """
    dump a list of RGB triplets to an RGB4 binary output file
    """
    aga = len(palette)>32
    nb = 0
    colreg = 0
    for r,g,b in palette:
        if not as_binary:
            if nb % 8 == 0:
                if nb:
                    f.write("\n")
                f.write("\tdc.w\t")
            else:
                f.write(",")
            nb+=1

        if low_nibble:
            value = ((r & 0xF) << 8) + ((g & 0xF) << 4) + (b & 0xF)
        else:
            value = ((r>>4) << 8) + ((g>>4) << 4) + (b>>4)
        if as_copperlist:
            bank,colmod = divmod(colreg,32)
            if colmod == 0 and aga:
                # issue bank
                params = (0x106,(bank<<13))
                if as_binary:
                    f.write(struct.pack(">HH",*params))
                else:
                    f.write("${:x},${:x}\n\tdc.w\t".format(*params))
            colout = colmod*2 + 0x180
            if as_binary:
                f.write(struct.pack(">HH",colout,value))
            else:
                f.write("${:04x},${:04x}".format(colout,value))
            colreg+=1
        else:
            if as_binary:
                f.write(struct.pack(">H",value))
            else:
                f.write("${:04x}".format(value))
    if not as_binary:
        f.write("\n")

def palette_dump(palette,output,as_copperlist=False,as_binary=False,high_precision=False):
    mode = "wb" if as_binary else "w"
    if high_precision:
        with open(output,mode) as f:
            # upper nibble
            __palette_dump(palette,f,as_copperlist=as_copperlist,as_binary=as_binary,low_nibble=False)
            if not as_copperlist and not as_binary:
                f.write("\t;lower nibble\n")
            __palette_dump(palette,f,as_copperlist=as_copperlist,as_binary=as_binary,low_nibble=True)
    else:
        with open(output,mode) as f:
            # upper nibble
            __palette_dump(palette,f,as_copperlist=as_copperlist,as_binary=as_binary,low_nibble=False)


def palette_extract(input_image,palette_precision_mask=0xFF):
    """
    extract the palette of an image
    palette_precision_mask: 0xFF: full RGB range, 0xF0: amiga ECS palette
    """
    if isinstance(input_image,str):
        imgorg = PIL.Image.open(input_image)
    else:
        imgorg = input_image

    # image could be paletted already. But we cannot trust palette order anyway
    width,height = imgorg.size
    img = PIL.Image.new('RGB', (width,height))
    img.paste(imgorg, (0,0))

    # count same colors
    rval = set()
    for y in range(height):
        for x in range(width):
            p = img.getpixel((x,y))
            p = tuple(x & palette_precision_mask for x in p)
            rval.add(p)
    return sorted(rval)

def palette_round(palette,mask=0xF0):
    """
    mask to match the lousy amiga resolution
    default mask is ECS
    """
    return [tuple(x & mask for x in e) for e in palette]

def palette_16bitbe2palette(data):
    rval = []
    for v in (data[i]*256+data[i+1] for i in range(0,len(data),2)):
        rval.append((((v & (0xF00))>>4),((v & (0xF0))),(v & (0xF))<<4))
    return rval

def palette_tojascpalette(rgblist,outfile):
    with open(outfile,"w") as f:
        f.write("JASC-PAL\n0100\n{}\n".format(len(rgblist)))
        for v in rgblist:
            f.write("{} {} {}\n".format(*v))



def palette_image2raw(input_image,output_filename,palette,add_dimensions=False,forced_nb_planes=None,palette_precision_mask=0xFF):
    """ rebuild raw bitplanes with palette (ordered) and any image which has
    the proper number of colors and color match
    pass None as output_filename to avoid writing to file
    returns image raw data
    palette_precision_mask: 0xFF: no mask, full precision when looking up the colors, 0xF0: ECS palette mask, or custom
    """
    # quick palette index lookup, with a privilege of the lowest color numbers
    # where there are duplicates (example: EHB emulated palette)
    palette_dict = {p:i for i,p in reversed(list(enumerate(palette)))}
    if isinstance(input_image,str):
        imgorg = PIL.Image.open(input_image)
    else:
        imgorg = input_image
    # image could be paletted already. But we cannot trust palette order anyway
    width,height = imgorg.size
    if width % 8:
        raise Exception("{} width must be a multiple of 8, found {}".format(input_image,width))
    img = PIL.Image.new('RGB', (width,height))
    img.paste(imgorg, (0,0))
    # number of planes is automatically converted from palette size
    min_nb_planes = int(math.ceil(math.log2(len(palette))))
    if forced_nb_planes:
        if min_nb_planes > forced_nb_planes:
            raise Exception("Minimum number of planes is {}, forced to {} (nb colors = {})".format(min_nb_planes,forced_nb_planes,len(palette)))
        nb_planes = forced_nb_planes
    else:
        nb_planes = min_nb_planes

    plane_size = height*width//8
    out = [0]*(nb_planes*plane_size)
    for y in range(height):
        for x in range(0,width,8):
            for i in range(8):
                offset = (y*width + x)//8
                porg = img.getpixel((x+i,y))

                p = tuple(x & palette_precision_mask for x in porg)
                try:
                    color_index = palette_dict[p]
                except KeyError:
                    # try to suggest close colors
                    approx = tuple(x&0xFE for x in p)
                    close_colors = [c for c in palette_dict if tuple(x&0xFE for x in c)==approx]

                    msg = "{}: (x={},y={}) rounded color {} not found, orig color {}, maybe try adjusting precision mask".format(
                input_image,x+i,y,p,porg)
                    msg += " {} close colors: {}".format(len(close_colors),close_colors)
                    raise Exception(msg)

                for pindex in range(nb_planes):
                    if color_index & (1<<pindex):
                        out[pindex*plane_size + offset] |= (1<<(7-i))

    out = bytes(out)

    if output_filename:
        with open(output_filename,"wb") as f:
            if add_dimensions:
                f.write(bytes((0,width//8,height>>8,height%256)))
            f.write(out)

    return out


def palette_image2sprite(input_image,output_filename,palette,palette_precision_mask=0xFF):
    """ rebuild raw bitplanes with palette (ordered) and any image which has
    the proper number of colors and color match
    pass None as output_filename to avoid writing to file
    returns image raw data
    palette_precision_mask: 0xFF: no mask, full precision when looking up the colors, 0xF0: ECS palette mask, or custom
    """
    if len(palette) != 4:
        raise Exception("Palette size must be 4")
    # quick palette index lookup, with a privilege of the lowest color numbers
    # where there are duplicates (example: EHB emulated palette)
    palette_dict = {p:i for i,p in reversed(list(enumerate(palette)))}
    if isinstance(input_image,str):
        imgorg = PIL.Image.open(input_image)
    else:
        imgorg = input_image
    # image could be paletted already. But we cannot trust palette order anyway
    width,height = imgorg.size
    if width != 16:
        raise Exception("{} width must be 16, found {}".format(input_image,width))
    img = PIL.Image.new('RGB', (width,height))
    img.paste(imgorg, (0,0))
    nb_planes = 2

    plane_size = height*width//8
    out = [0]*(nb_planes*plane_size)
    for y in range(height):
        for x in range(0,width,8):
            for i in range(8):
                porg = img.getpixel((x+i,y))

                p = tuple(x & palette_precision_mask for x in porg)
                try:
                    color_index = palette_dict[p]
                except KeyError:
                    # try to suggest close colors
                    approx = tuple(x&0xFE for x in p)
                    close_colors = [c for c in palette_dict if tuple(x&0xFE for x in c)==approx]

                    msg = "{}: (x={},y={}) rounded color {} not found, orig color {}, maybe try adjusting precision mask".format(
                input_image,x+i,y,p,porg)
                    msg += " {} close colors: {}".format(len(close_colors),close_colors)
                    raise Exception(msg)

                for pindex in range(nb_planes):
                    if color_index & (1<<pindex):
                        out[(((y*nb_planes)+pindex)*width + x)//8] |= (1<<(7-i))

    out = bytes(out)

    if output_filename:
        with open(output_filename,"wb") as f:
##            if add_dimensions:
##                f.write(bytes((0,width//8,height>>8,height%256)))
            f.write(out)

    return out

