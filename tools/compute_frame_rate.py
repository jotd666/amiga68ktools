import argparse,glob,os
from PIL import Image
from PIL import ImageChops

# computes frame rate by checking at which rate the image changes

parser = argparse.ArgumentParser()
##    parser.add_argument("--input", help="output file",type=str, required=True)
##    parser.add_argument("--output", help="output file",type=str, required=True)
parser.add_argument("input_directory",help="input directory")

args = parser.parse_args()

previous_img = None
nb_times_equal = 0
result = []
for image in sorted(glob.glob(os.path.join(args.input_directory,"*.png"))):
    img = Image.open(image)
    if previous_img:
        diff = ImageChops.difference(img,previous_img)
        if diff.getbbox():
            if nb_times_equal > 10:
                # ignore
                pass
            else:
                result.append(nb_times_equal)
            nb_times_equal=0
        else:
            nb_times_equal+=1

    previous_img = img

print("Average frame rate: {}".format(sum(result)/len(result)))