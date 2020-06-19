import glob,os,subprocess,io,math,sys

temp_dir = os.getenv("TEMP","/tmp")
temp_ppm = os.path.join(temp_dir,"temp.ppm")
temp2_ppm = os.path.join(temp_dir,"temp2.ppm")

target_width,target_height = (640,200)

def nb_to_pow2(x):
    return (int(math.ceil(math.log2(x))))

def get_image_info(image_data):
    if isinstance(image_data,str):
        ext = os.path.splitext(image_data)[1]
        if ext==".iff":
            image_data = subprocess.check_output(["ilbmtoppm",image_data])
        elif ext==".ppm":
            with open(image_data,"rb") as f:
                image_data = f.read()
        else:
            raise Exception("Unknown extension {}".format(ext))

    fio = io.BytesIO(image_data)

    imgtype = next(fio).decode("ascii").strip()
    if imgtype!="P6":
        raise Exception("Unsupported format {}".format(imgtype))
    width,height = map(int,next(fio).decode("ascii").split())

    next(fio)
    data = iter(fio.read(width*height*3))
    rgb_set = {(next(data),next(data),next(data)) for _ in range(width*height)}
    fio.close()

    return width,height,len(rgb_set)

def convert_ppm_to_iff(output,nb_colors,optimize_depth,verbose=False):
    # can't be higher than 128 colors
    if optimize_depth:
        nb_planes = min(7,nb_to_pow2(nb_colors))
    else:
        nb_planes = 7

    nb_rounded_colors = 2**nb_planes
    with open(temp_ppm,"wb") as f:
        f.write(output)
    # convert image without any aspect ratio preservation & no antialias (preserves number of colors)
    args = ["imconvert",temp_ppm,"-scale","{}x{}!".format(target_width,target_height),"-colors",str(nb_rounded_colors),temp2_ppm]
    subprocess.check_call(args)
    return subprocess.check_output(["ppmtoilbm","-mp",str(nb_planes),temp2_ppm])

def convert_iff(iff_image,optimize_depth=False,pretend=False,force=False):
    output = subprocess.check_output(["ilbmtoppm",iff_image])

    # optimizing the palette is not really needed but it allows to irfanview iff
    # plugin to be able to display the images (with 256/8 it fails, even if OK on real miggy)
    # as a bonus, images are displayable on ECS amigas
    width,height,nb_colors = get_image_info(output)

    if not force and (width,height) == (target_width,target_height):
        # no need to convert: the size is already OK
        return [False,"size"]

    iff_data = convert_ppm_to_iff(output,nb_colors,optimize_depth)

    if pretend:
        return [False,"pretend mode"]
    else:
        with open(iff_image,"wb") as f:
            f.write(iff_data)
        return [True,"OK"]

def convert_png(png_image,optimize_depth=False,pretend=False):
    output = subprocess.check_output(["pngtopnm",png_image])
    # output is now a pnm image. We write it in temp
    width,height,nb_colors = get_image_info(output)

    iff_data = convert_iff_to_ppm(output,nb_colors,optimize_depth)
    bn = os.path.splitext(os.path.basename(png_image))[0]
    iff_dir = os.path.join(os.path.dirname(os.path.dirname(png_image)),bn[0].upper(),bn.title())
    iff_image = os.path.join(iff_dir,"igame.iff")
    if pretend:
        return [False,"pretend to write {}".format(iff_image)]
    else:
        if os.path.isdir(iff_dir):
            pass
        else:
            os.makedirs(iff_dir)

        with open(iff_image,"wb") as f:
            f.write(iff_data)
        return [True,"OK"]

def png2iff():
    progdir = os.path.dirname(__file__)
    for i in glob.glob(os.path.join(progdir,"..","data","images","_png","*.png")):
        sys.stdout.write("processing {} ...".format(i))
        status,reason = convert_png(i,optimize_depth=True,pretend=False)
        if not status:
            print("not done ({})".format(reason))
        else:
            j = os.path.join(os.path.dirname(os.path.dirname(i)),"_png_done",os.path.basename(i))
            os.rename(i,j)
            print("OK")

def iffconv():
    progdir = os.path.dirname(__file__)
    for i in glob.glob(os.path.join(progdir,"..","data","images","*","*","*.iff")):
        sys.stdout.write("processing {} ...".format(i))
        status,reason = convert_iff(i,optimize_depth=True,pretend=False)
        if not status:
            print("not done ({})".format(reason))
        else:
            print("OK")

if __name__=="__main__":
    i = r"K:\jff\data\python\compilation_maker\data\images\A\AddamsFamily\igame.iff"
    convert_iff(i,True,False,True)
    print(temp2_ppm)
##    try:
##        os.remove(temp_ppm)
##        os.remove(temp2_ppm)
##    except IOError:
##        pass
