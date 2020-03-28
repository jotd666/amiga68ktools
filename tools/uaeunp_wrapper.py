import os,sys,re,glob,subprocess
import getopt,traceback
#import count_usage

import fnmatch,shutil

class Template:
    __VERSION_NUMBER = "1.0"
    __MODULE_FILE = __file__
    __PROGRAM_NAME = os.path.basename(__MODULE_FILE)
    __PROGRAM_DIR = os.path.abspath(os.path.dirname(__MODULE_FILE))

    def __init__(self):
        self.__logfile = ""
        # init members with default values
        self.__input_file = []
        self.__output_directory = ""

    def init_from_sys_args(self,debug_mode = True):
        """ standalone mode """

        try:
            self.__do_init()
        except:
          if sys.exc_info()[0] != SystemExit:
            if debug_mode:
                # get full exception traceback
                traceback.print_exc()
            else:
                self.__message(str(sys.exc_info()[1]))

            sys.exit(1)

# uncomment if module mode is required
##    def init(self,my_arg_1):
##        """ module mode """
##        # set the object parameters using passed arguments
##        self.__output_file = my_arg_1
##        self.__doit()

    def __do_init(self):
        self.__opts = None
        self.__args = None
        #count_usage.count_usage(self.__PROGRAM_NAME,1)
        self.__parse_args()
        self.__doit()

    def __purge_log(self):
        if self.__logfile != "":
            try:
                os.remove(self.__logfile)
            except:
                pass

    def __message(self,msg):
        msg = self.__PROGRAM_NAME+(": %s" % msg)+os.linesep
        sys.stderr.write(msg)
        if self.__logfile:
            f = open(self.__logfile,"a")
            f.write(msg)
            f.close()

    def __error(self,msg):
        raise Exception("Error: "+msg)

    def __warn(self,msg):
        self.__message("Warning: "+msg)


    def __parse_args(self):
         # Command definition
         # Prepare short & long args from list to avoid duplicate info

        self.__opt_string = ""

        longopts_eq = ["version","help","input-file=","output-file="]

        self.__shortopts = []
        self.__longopts = []
        sostr = ""

        for o in longopts_eq:
            i = o[0]

            has_args = o.endswith("=")

            if has_args:
                i += ":"
                o = o[:-1]

            sostr += i
            self.__opt_string += " -"+o[0]+"|--"+o
            if has_args:
                self.__opt_string +=" <>"


            self.__shortopts.append(i)
            self.__longopts.append(o)  # without "equal"

        self.__opts, self.__args = getopt.getopt(sys.argv[1:], sostr,longopts_eq)


        # Command options
        for option, value in self.__opts:
            oi = 0
            if option in ('-v','--'+self.__longopts[oi]):
                print(self.__PROGRAM_NAME + " v" + self.__VERSION_NUMBER)
                sys.exit(0)
            oi += 1
            if option in ('-h','--'+self.__longopts[oi]):
                self.__usage()
                sys.exit(0)
            oi += 1
            if option in ('-i','--'+self.__longopts[oi]):
                self.__input_file.extend(glob.glob(value))
            oi += 1
            if option in ('-o','--'+self.__longopts[oi]):
                self.__output_directory = value

        if not self.__input_file:
            self.__error("input file not set")

    def __usage(self):

        sys.stderr.write("Usage: "+self.__PROGRAM_NAME+self.__opt_string+os.linesep)


    def __doit(self):
        for fp in self.__input_file:
            f = os.path.basename(fp)
            the_dir = os.path.dirname(fp) or None
            p,e = os.path.splitext(f)
            if e.lower().endswith(".adf"):
                continue
            args = ["uaeunp.exe",f,p+".adf"]
            print(" ".join(args))
            subprocess.check_call(args,cwd=the_dir)

if __name__ == '__main__':
    """
        Description :
            Main application body
    """


    o = Template()
    o.init_from_sys_args(debug_mode = True)
    #o.init("output_file")
