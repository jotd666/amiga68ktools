import bitplanelib
from PIL import Image

img = Image.open("input.png")
palette = bitplanelib.palette_extract(img)
print(palette)
raw = bitplanelib.palette_image2raw(img,None,palette,generate_mask=True,forced_nb_planes=4)

img = Image.open("input_magenta.png")

raw2 = bitplanelib.palette_image2raw(img,None,palette,forced_nb_planes=4,generate_mask=True,mask_color=(255,0,255))

print(raw==raw2)