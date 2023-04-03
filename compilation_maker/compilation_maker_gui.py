import sys,os,glob
import wx_generic_gui_frame,wx_utils
from collections import OrderedDict
import compilation_maker

class MyApp(wx_generic_gui_frame.GenericApp):
    __VERSION_NUMBER = "1.2"
    __MODULE_FILE = __file__ if not hasattr(sys,'frozen') else sys.executable
    __PROGRAM_NAME = "CD/HD compilation maker (GUI)"
    __PROGRAM_DIR = os.path.abspath(os.path.dirname(__MODULE_FILE))

    __FIELD_DATA_ROOT_DIR = "Data directory"
    __FIELD_DATABASE_FILE = "Opts DB filepath"
    __FIELD_PROGRAM_TO_RUN = "Program to run"
    __FIELD_SAVE_MISSING_DATABASE_FILE = "Save miss DB info"
    __FIELD_KICKSTARTS_DIRECTORY = "Kicks directory"
    __FIELD_GAME_DEMO_DATA_SUBDIR = "Game/demo data subdir"
    __FIELD_MISSING_DATABASE_FILE = "Missing DB filepath"
    __FIELD_MASTER_QUIT_KEY = "Master quit key"

    __PROGRAM_TO_RUN = {"WHDload":"whdload","CD32Load (IDE HD)":"cd32load_hd","CD32Load (CD)":"cd32load","jst":"jst"}

    def __init__(self):
        wx_generic_gui_frame.GenericApp.__init__(self)


    def _init(self):
        params = OrderedDict()
        keycode_dict = OrderedDict()
        keycode_dict["NONE"] = 0x00
        keycode_dict["HELP"] = 0x5F
        keycode_dict["TAB"] = 0x42
        keycode_dict["NUM -"] = 0x5C
        keycode_dict["F9"] = 0x58
        self.__keycode_dict = keycode_dict

        params[self.__FIELD_DATA_ROOT_DIR] = ""
        params[self.__FIELD_GAME_DEMO_DATA_SUBDIR] = "GAMES"
        params[self.__FIELD_DATABASE_FILE] = os.path.join(self.__PROGRAM_DIR,"gameinfo.csv")
        params[self.__FIELD_PROGRAM_TO_RUN] = sorted(self.__PROGRAM_TO_RUN.keys())
        params[self.__FIELD_MASTER_QUIT_KEY] = list(keycode_dict)
        params[self.__FIELD_SAVE_MISSING_DATABASE_FILE] = False
        params[self.__FIELD_KICKSTARTS_DIRECTORY] = ""
        params[self.__FIELD_MISSING_DATABASE_FILE] = ""



        program_name =os.path.splitext(self.__PROGRAM_NAME)[0]
        main = self.register_frame(wx_generic_gui_frame.GenericGuiFrame(parent=None,params=params,callback=self.__callback,width = 600, label_width = 150, widget_height=35,persist_as=program_name))
        self.set_title(program_name+" "+self.__VERSION_NUMBER)

        f=self.get_frame()
        f.set_tooltip_string(self.__FIELD_DATA_ROOT_DIR,"Root directory where AGS, c, s, libs ... will be created/updated")
        f.set_tooltip_string(self.__FIELD_GAME_DEMO_DATA_SUBDIR,"Comma-separated subdir name(s)/wildcard(s) where to look for games from the root directory")
        f.set_tooltip_string(self.__FIELD_DATABASE_FILE,"database file used to add options to each game (mainly for CD32 controls, optional)")
        f.set_tooltip_string(self.__FIELD_PROGRAM_TO_RUN,"which program/context is used to run the games. WHDload is used when you have fastmem, CD32load is used to\n"
        "create ISO files for CD32, CD32load HD is used to create FFS partitions on vanilla 2MB A1200s")
        f.set_tooltip_string(self.__FIELD_KICKSTARTS_DIRECTORY,"kickstart files cannot be provided for legal reasons. Provide the directory where you're storing them")
        self.__update_widgets()

    def __update_widgets(self):
        pass
    def __modified_output(self,k,widget):
        self.__update_widgets()

    def __callback(self,params):

        root_dir = params[self.__FIELD_DATA_ROOT_DIR]
        if not root_dir:
            raise Exception("Root dir is empty")

        args = ["-r",root_dir]
        kickstarts_dir = params[self.__FIELD_KICKSTARTS_DIRECTORY]
        game_subdir_pattern = params[self.__FIELD_GAME_DEMO_DATA_SUBDIR]
        args += ["-s",game_subdir_pattern]
        if kickstarts_dir:
            args += ["-k",kickstarts_dir]
        database_file = params[self.__FIELD_DATABASE_FILE]
        if database_file:
            args += ["-d",database_file]
        program_to_run = params[self.__FIELD_PROGRAM_TO_RUN]
        args += ["-p",self.__PROGRAM_TO_RUN[program_to_run]]
        if params[self.__FIELD_SAVE_MISSING_DATABASE_FILE]:
            args += ["-m",params[self.__FIELD_MISSING_DATABASE_FILE]]
        qk = params[self.__FIELD_MASTER_QUIT_KEY]
        qk = self.__keycode_dict.get(qk)
        if qk:
            args += ["-M",str(qk)]

        compilation_maker.doit(args)
        wx_utils.info_message("Done")

def main():
    application = MyApp()

if __name__ == '__main__':
    main()
