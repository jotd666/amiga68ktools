import PIL.Image,math

def bitplanes_raw2image(contents,nb_planes,width,height,output_filename,palette):

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

    img.save(output_filename)

def bitplanes_raw2planarimage(contents,nb_planes,width,height,output_filename):

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

    img.save(output_filename)

def bitplanes_planarimage2raw(input_imagename,nb_planes,output_filename):
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
    with open(output_filename,"wb") as f:
        f.write(bytes(out))


def palette_regdump2palette(text):
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

def palette_extract(input_image,amigaized = True):
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
            if amigaized:
                p = tuple(x & 0xF0 for x in p)
            rval.add(p)
    return sorted(rval)

def palette_amigaize(palette):
    """
    mask to match the lousy amiga resolution
    """
    return [tuple(x & 0xF0 for x in e) for e in palette]

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

def palette_image2raw(input_imagename,output_filename,palette,add_dimensions=True):
    """ rebuild raw bitplanes with palette (ordered) and any image which has
    the proper number of colors and color match
    """
    # quick palette index lookup
    palette_dict = {p:i for i,p in enumerate(palette)}
    imgorg = PIL.Image.open(input_imagename)
    # image could be paletted already. But we cannot trust palette order anyway
    width,height = imgorg.size
    if width % 8:
        raise Exception("{} width must be a multiple of 8, found {}".format(input_imagename,width))
    img = PIL.Image.new('RGB', (width,height))
    img.paste(imgorg, (0,0))
    # number of planes is automatically converted from palette size
    nb_planes = int(math.log2(len(palette)))
    plane_size = height*width//8
    out = [0]*(nb_planes*plane_size)
    for y in range(height):
        for x in range(0,width,8):
            for i in range(8):
                offset = (y*width + x)//8
                porg = img.getpixel((x+i,y))
                p = tuple(x & 0xF0 for x in porg)
                try:
                    color_index = palette_dict[p]
                except KeyError:
                    raise Exception("{}: (x={},y={}) rounded color {} not found, orig color {}".format(
                input_imagename,x+i,y,p,porg))
                for pindex in range(nb_planes):
                    if color_index & (1<<pindex):
                        out[pindex*plane_size + offset] |= (1<<(7-i))

    with open(output_filename,"wb") as f:
        if add_dimensions:
            f.write(bytes((0,width//8,height>>8,height%256)))
        f.write(bytes(out))
