import py2exe,sys,os,glob,shutil
import wx_generic_gui

images = glob.glob(os.path.join(os.path.dirname(wx_generic_gui.__file__),"*.png"))

dist_dir = "dist"
output_dir = os.path.join(dist_dir,"data")

if os.path.isdir(dist_dir):
    shutil.rmtree(dist_dir)
if os.path.isdir(output_dir):
    shutil.rmtree(output_dir)
source_dir = os.path.join(dist_dir,"src")
if os.path.isdir(source_dir):
    shutil.rmtree(source_dir)

os.makedirs(output_dir)
os.mkdir(source_dir)

from distutils.core import setup
sys.argv = [__file__,"py2exe","--dist-dir",output_dir]
setup(console=["compilation_maker_gui.py"])


for i in images:
    shutil.copy(i,output_dir)
for f in ["readme.txt","gameinfo.csv"]:
    shutil.copy(f,output_dir)

# copy source files

for s in glob.glob("*.py"):
    shutil.copy(s,source_dir)
shutil.copytree("extras",os.path.join(source_dir,"extras"))

shutil.copytree("data",os.path.join(output_dir,"data"))
shutil.copytree("HDROOT_DEMO",os.path.join(dist_dir,"HDROOT_DEMO"))

with open(os.path.join(dist_dir,"cm.bat"),"w") as f:
    f.write("@echo off\n%~pd0\\data\\compilation_maker_gui.exe")


