#!/usr/bin/env python
import sys,os,glob,subprocess
import wx_generic_gui_frame,wx_utils
from collections import OrderedDict

import export_levels,update_diskfile

class MyApp(wx_generic_gui_frame.GenericApp):
    __VERSION_NUMBER = "1.0"
    __MODULE_FILE = __file__
    __PROGRAM_NAME = "Magic Pockets level exporter (GUI)"
    __PROGRAM_DIR = os.path.abspath(os.path.dirname(__MODULE_FILE))
    __RNC_PACK = os.path.join(__PROGRAM_DIR,"rnc.exe")
    __RNC_UNPACK = os.path.join(__PROGRAM_DIR,"dernc.exe")

    __FIELD_TARGET_VERSION = "Target version"
    __FIELD_SOURCE_LEVEL_SET = "Source level set"
    __FIELD_OUTPUT_DIRECTORY = "Output directory"


    def __init__(self):
        wx_generic_gui_frame.GenericApp.__init__(self)


    def _init(self):
        self.__target_version = ["MS-DOS","MS-DOS (packed files)","Amiga NTSC/US","Amiga NTSC/US (copy diskimage)"]
        self.__source_level_set = [os.path.basename(x) for x in glob.iglob(os.path.join(export_levels.levels_root,"*")) if os.path.isdir(x)]

        params = OrderedDict()
        params[self.__FIELD_TARGET_VERSION] = self.__target_version
        params[self.__FIELD_SOURCE_LEVEL_SET] = self.__source_level_set
        params[self.__FIELD_OUTPUT_DIRECTORY] = ""


        program_name =os.path.splitext(self.__PROGRAM_NAME)[0]
        main = self.register_frame(wx_generic_gui_frame.GenericGuiFrame(parent=None,params=params,callback=self.__callback,persist_as=program_name))
        self.set_title(program_name+" "+self.__VERSION_NUMBER)

        f=self.get_frame()
        f.set_tooltip_string(self.__FIELD_TARGET_VERSION,"Amiga: update existing 'disk.1', Amiga (copy): create 'disk.1.new' in the same dir")
        f.set_tooltip_string(self.__FIELD_OUTPUT_DIRECTORY,"Select/drag'n'drop MS-DOS game root dir / directory where to find 'disk.1' file")
        self.__update_widgets()

    def __update_widgets(self):
        pass
    def __modified_output(self,k,widget):
        self.__update_widgets()

    def __callback(self,params):
        target_version = params[self.__FIELD_TARGET_VERSION]
        output_directory = params[self.__FIELD_OUTPUT_DIRECTORY]
        source_level_set = params[self.__FIELD_SOURCE_LEVEL_SET]

        if target_version.startswith("MS-DOS"):
            # check if output dir has the "data" subdir
            datadir = os.path.join(output_directory,"DATA")
            if os.path.exists(datadir):
                pass
            else:
                raise Exception("Subdir {} not found".format(datadir))
            # now generate files, directly in the subdir

            generated_files = export_levels.doit(source_level_set,datadir)

            if "packed" in target_version:
                print("Packing files...")
                # if packed, call rnc packer
                p = subprocess.Popen([self.__RNC_PACK]+generated_files,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,cwd=datadir)
                rc = p.wait()
                if rc:
                    raise Exception("cannot pack: {}".format(p.stdout.read()))

            wx_utils.info_message("Export completed successfully")


        elif target_version.startswith("Amiga"):
            # check diskimage
            diskfile = os.path.join(output_directory,"disk.1")
            if not os.path.exists(diskfile):
                raise Exception("in/out diskfile 'disk.1' not found in {}".format(output_directory))
            temp_dir = os.path.join(os.getenv("TEMP"),"mplevels")
            if not os.path.isdir(temp_dir):
                os.mkdir(temp_dir)


def main():
    application = MyApp()

if __name__ == '__main__':
    main()
