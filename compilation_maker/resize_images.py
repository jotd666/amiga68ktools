import glob,os,subprocess,io,math

temp_dir = os.getenv("TEMP")
temp_ppm = os.path.join(temp_dir,"temp.ppm")
temp2_ppm = os.path.join(temp_dir,"temp2.ppm")
od = os.getenv("TEMP")

def nb_to_pow2(x):
    return (int(math.ceil(math.log2(x))))

def get_nb_colors(image_data):
    fio = io.BytesIO(image_data)

    imgtype = next(fio).decode("ascii").strip()
    if imgtype!="P6":
        raise Exception("Unsupported format {}".format(imgtype))
    x,y = map(int,next(fio).decode("ascii").split())

    next(fio)
    data = iter(fio.read(x*y*3))
    rgb_set = {(next(data),next(data),next(data)) for _ in range(x*y)}
    return len(rgb_set)

def convert(iff_image,optimize_depth=False,pretend=False):
    output = subprocess.check_output(["ilbmtoppm",iff_image])

    # optimizing the palette is not really needed but it allows to irfanview iff
    # plugin to be able to display the images (with 256/8 it fails, even if OK on real miggy)
    # as a bonus, images are displayable on ECS amigas
    if optimize_depth:
        nb_colors = get_nb_colors(output)
        nb_planes = nb_to_pow2(nb_colors)
    else:
        nb_planes = 8

    nb_rounded_colors = 2**nb_planes

    with open(temp_ppm,"wb") as f:
        f.write(output)
    # convert image without any aspect ratio preservation & no antialias (preserves number of colors)
    subprocess.check_call(["imconvert",temp_ppm,"-scale","640x200!","-colors",str(nb_rounded_colors),temp2_ppm])
    output = subprocess.check_output(["ppmtoilbm","-mp",str(nb_planes),temp2_ppm])
    if pretend:
        pass
    else:
        with open(iff_image,"wb") as f:
            f.write(output)

if __name__=="__main__":
    for i in glob.glob(r"data\images\*\*\*.iff"):
        print("processing %s"%i)
        convert(i,optimize_depth=True)

    os.remove(temp_ppm)
    os.remove(temp2_ppm)
