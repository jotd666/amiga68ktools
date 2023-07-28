import PIL.Image,math,struct,json

PALETTE_FORMAT_ASMMOT = 1
PALETTE_FORMAT_ASMGNU = 1<<1
PALETTE_FORMAT_BINARY = 1<<2
PALETTE_FORMAT_COPPERLIST = 1<<3
PALETTE_FORMAT_PNG = 1<<4

class BitplaneException(Exception):
    pass

def closest_color(c1,colorlist):
    """
    c1: rgb of color to approach
    colorlist: list of rgb tuples of the palette
    returns: one of the colors of colorlist

    probably not the best algorithm but...
    """
    closest = None
    min_dist = (255*255)*3
    # not sure this is the best: compute square distance in RGB diff
    for c in colorlist:
        dist = sum((x1-x2)*(x1-x2) for x1,x2 in zip(c,c1))
        if dist < min_dist:
            min_dist = dist
            closest = c
    return closest

def dump_asm_bytes(block,f,mit_format=False,nb_elements_per_row=8,size=1):
    c = 0
    hs = "0x" if mit_format else "$"
    for d in block:
        if c==0:
            array = ({1:".byte",2:".word",4:".long"} if mit_format else
            {1:"dc.b",2:"dc.w",4:"dc.l"})
            f.write("\n\t{}\t".format(array[size]))
        else:
            f.write(",")
        f.write("{}{:0{}x}".format(hs,d,size*2))
        c += 1
        if c == nb_elements_per_row:
            c = 0
    f.write("\n")

def palette_load_from_json(filename):
    with open(filename) as f:
        p = [tuple(x) for x in json.load(f)]
    return p

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

def round_color(rgb,mask):
    return tuple(p & mask for p in rgb)

def to_rgb4_color(rgb):
    return ((rgb[0]>>4)<<8) + ((rgb[1] >>4)<<4) +(rgb[2]>>4)

def rgb4_to_rgb_triplet(rgb4):
    return tuple((x<<4) for x in ((rgb4&0xF00)>>8,(rgb4&0xF0)>>4,rgb4&0xF))

def palette_regdump2palette(text):
    """ converts a winuae custom register dump (e command) to a palette
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

def __palette_dump(palette,f,pformat,low_nibble):
    """
    dump a list of RGB triplets to an RGB4 binary output file
    """
    aga = len(palette)>32
    nb = 0
    colreg = 0
    dcw = "dc.w" if pformat & PALETTE_FORMAT_ASMMOT else ".word"
    hexs = "$" if pformat & PALETTE_FORMAT_ASMMOT else "0x"

    for r,g,b in palette:
        if (pformat & PALETTE_FORMAT_BINARY) == 0:
            if nb % 8 == 0:
                if nb:
                    f.write("\n")
                f.write("\t{}\t".format(dcw))
            else:
                f.write(",")
            nb+=1

        if low_nibble:
            value = ((r & 0xF) << 8) + ((g & 0xF) << 4) + (b & 0xF)
        else:
            value = ((r>>4) << 8) + ((g>>4) << 4) + (b>>4)
        if pformat & PALETTE_FORMAT_COPPERLIST:
            bank,colmod = divmod(colreg,32)
            if colmod == 0 and aga:
                # issue bank
                params = (0x106,(bank<<13))
                if as_binary:
                    f.write(struct.pack(">HH",*params))
                else:
                    f.write("{3}{0:x},{3}{1:x}\n\t{2}\t".format(params[0],params[1],dcw,hexs))
            colout = colmod*2 + 0x180
            if pformat & PALETTE_FORMAT_BINARY:
                f.write(struct.pack(">HH",colout,value))
            else:
                f.write("{2}{0:04x},{2}{1:04x}".format(colout,value,hexs))
            colreg+=1
        else:
            if pformat & PALETTE_FORMAT_BINARY:
                f.write(struct.pack(">H",value))
            else:
                f.write("{}{:04x}".format(hexs,value))
    if not pformat & PALETTE_FORMAT_BINARY:
        f.write("\n")


def palette_to_image(palette,output):
    sqs = 16
    width = sqs*len(palette)
    height = sqs
    img = PIL.Image.new('RGB', (width,height))
    x = 0
    for rgb in palette:
        for i in range(16):
            for j in range(16):
                img.putpixel((i+x,j),rgb)
        x += sqs

    img.save(output)

def palette_dump(palette,output,pformat=PALETTE_FORMAT_ASMMOT,high_precision=False):
    """
    output: string (filename to write into) or open file handle (in writing)
    """
    if pformat & PALETTE_FORMAT_PNG:
        # special case: png dump
        palette_to_image(palette,output)
    else:
        as_binary = pformat & PALETTE_FORMAT_BINARY
        mode = "wb" if as_binary else "w"
        if isinstance(output,str):
            f = open(output,mode)
        else:
            f = output
        if high_precision:
            # upper nibble
            __palette_dump(palette,f,pformat=pformat,low_nibble=False)
            if not pformat & PALETTE_FORMAT_COPPERLIST and not as_binary:

                f.write("\t{}lower nibble\n".format(";" if pformat & PALETTE_FORMAT_ASMMOT else "*"))
            __palette_dump(palette,f,pformat,low_nibble=True)
        else:
            # upper nibble
            __palette_dump(palette,f,pformat,low_nibble=False)
        if isinstance(output,str):
            f.close()

def palette_extract(input_image,palette_precision_mask=0xFF):
    """
    extract the palette of an image
    palette_precision_mask: 0xFF: full RGB range, 0xF0: amiga ECS palette
    sort palette (order isn't preserved in pngs anyway) so black is first
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

def palette_rgb42palette(data):
    return [((((v & (0xF00))>>4),((v & (0xF0))),(v & (0xF))<<4)) for v in data]


def palette_tojascpalette(rgblist,outfile):
    with open(outfile,"w") as f:
        f.write("JASC-PAL\n0100\n{}\n".format(len(rgblist)))
        for v in rgblist:
            f.write("{} {} {}\n".format(*v))


def palette_fromjascpalette(infile,rgb_mask=0xFF):
    with open(infile,"r") as f:
        header = next(f)
        if header != "JASC-PAL\n":
            raise BitplaneException("No header")
        next(f)
        nb_colors = int(next(f))
        return [[int(x) & rgb_mask for x in next(f).split()] for _ in range(nb_colors)]



def palette_image2raw(input_image,output_filename,palette,add_dimensions=False,forced_nb_planes=None,
                    palette_precision_mask=0xFF,generate_mask=False,blit_pad=False,mask_color=(0,0,0)):
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

    if blit_pad:
        r = width % 16
        if r:
            width += 16-r
        width += 16
    img = PIL.Image.new('RGB', (width,height), mask_color if generate_mask else 0)
    img.paste(imgorg, (0,0))

    if width % 8:
        raise BitplaneException("{} width must be a multiple of 8, found {}".format(input_image,width))


    # number of planes is automatically converted from palette size
    min_nb_planes = int(math.ceil(math.log2(len(palette))))
    if forced_nb_planes:
        if min_nb_planes > forced_nb_planes:
            raise BitplaneException("Minimum number of planes is {}, forced to {} (nb colors = {})".format(min_nb_planes,forced_nb_planes,len(palette)))
        nb_planes = forced_nb_planes
    else:
        nb_planes = min_nb_planes

    def html(p):
        return ("{:02x}"*3).format(*p)
    plane_size = height*width//8

    actual_nb_planes = nb_planes
    if generate_mask:
        actual_nb_planes+=1

    out = [0]*(actual_nb_planes*plane_size)
    for y in range(height):
        for xb in range(0,width,8):
            for i in range(8):
                x = xb+i
                bitset = (1<<(7-i))
                offset = (y*width + x)//8
                porg = img.getpixel((x,y))
                if porg != mask_color:
                    if generate_mask:
                        # any non-mask color: set bit in mask
                        out[nb_planes*plane_size + offset] |= bitset

                    p = tuple(x & palette_precision_mask for x in porg)
                    try:
                        color_index = palette_dict[p]
                    except KeyError:
                        # try to suggest close colors
                        approx = tuple(x&0xFE for x in p)
                        close_colors = [c for c in palette_dict if tuple(x&0xFE for x in c)==approx]

                        msg = "{}: (x={},y={}) rounded color {} (#{}) not found, orig color {} (#{}), maybe try adjusting precision mask".format(
                    input_image,x,y,p,html(p),porg,html(porg))
                        msg += " {} close colors: {}".format(len(close_colors),close_colors)
                        raise BitplaneException(msg)

                    for pindex in range(nb_planes):
                        if color_index & (1<<pindex):
                            out[pindex*plane_size + offset] |= bitset


    out = bytes(out)

    if output_filename:
        with open(output_filename,"wb") as f:
            if add_dimensions:
                f.write(bytes((0,width//8,height>>8,height%256)))
            f.write(out)

    return out


def palette_image2sprite(input_image,output_filename,palette,palette_precision_mask=0xFF,sprite_fmode=0):
    """ rebuild raw bitplanes with palette (ordered) and any image which has
    the proper number of colors and color match
    pass None as output_filename to avoid writing to file
    returns image raw data
    palette_precision_mask: 0xFF: no mask, full precision when looking up the colors, 0xF0: ECS palette mask, or custom
    sprite_fmode = 0 for OCS/ECS (16-bit wide), 1 & 2 (32-bit wide, unsupported), 3 (64-bit wide)
    """
    if len(palette) != 4:
        raise BitplaneException("Palette size must be 4")
    # quick palette index lookup, with a privilege of the lowest color numbers
    # where there are duplicates (example: EHB emulated palette)
    palette_dict = {p:i for i,p in reversed(list(enumerate(palette)))}
    if isinstance(input_image,str):
        imgorg = PIL.Image.open(input_image)
    else:
        imgorg = input_image
    # image could be paletted already. But we cannot trust palette order anyway
    img_width,height = imgorg.size
    width = {0:16,1:32,2:32,3:64}[sprite_fmode]
    if img_width > width:
        raise BitplaneException("{} width must be <= {}, found {}".format(input_image,width,img_width))
    # convert to RGB and pad width if needed (16 bit wide sprite will be 64 bit wide in fmode=3)
    img = PIL.Image.new('RGB', (width,height),palette[0])
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

                    msg = "{}: (x={},y={}) rounded color {} not found, orig color {}, maybe try adjusting precision mask (current: 0x{:x})".format(
                input_image,x+i,y,p,porg,palette_precision_mask)
                    msg += " {} close colors: {}".format(len(close_colors),close_colors)
                    raise BitplaneException(msg)

                for pindex in range(nb_planes):
                    if color_index & (1<<pindex):
                        out[(((y*nb_planes)+pindex)*width + x)//8] |= (1<<(7-i))

    out = bytes(out)

    if output_filename:
        with open(output_filename,"wb") as f:
            f.write(out)

    return out

def print_long_hex_array(array):
    print( " ".join(["".join("{:02x}".format(array[i]) for i in range(j,j+4)) for j in range(0,len(array),4)]))

