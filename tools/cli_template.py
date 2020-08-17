try:
    import colorama

    colorama.init()
except Exception:
    # color won't be available, bummer!
    class colorama:
        class Fore:
            RED = ""
            YELLOW = ""
            RESET = ""
            LIGHTRED_EX = ""

# standard imports
import os, sys, threading, glob
import argparse, traceback





class ArgParser(object):
    def __init__(self, program_name, version):
        self.__parser = argparse.ArgumentParser(prog=program_name, add_help=True)
        self.__main_group = self.__parser.add_argument_group("Specific arguments")
        self.__parser.add_argument('-v', '--version', action='version', version=version)

    def add_argument(self, long_opt, desc, short_opt=None, required=False, default=None, *args, **kwargs):
        # For easy writting, user use '=' at param name end if it receive a value
        # And omit it if this parameter is just a flag
        #
        # All the standard parameters of argparse.ArgumentParser().add_argument() are also accepted :
        # eg. self.__ARG_PARSER.add_argument("max-lines", "Maximum number of lines", type=int)
        # => the max_lines parameter will automatically be converted to an integer
        #
        if long_opt.endswith('='):
            # Store linked value
            action = "store"
            # Remove the '=' at end to normalize
            long_opt = long_opt[:-1]
        elif long_opt.endswith('=[]'):
            # Store in an array
            action = "append"
            if default is None:
                default = []
            # Remove the '=[]' at end to normalize
            long_opt = long_opt[:-3]
        else:
            # Flag mode
            action = "store_true"
            if default is None:
                default = False

        if not short_opt:
            short_opt = long_opt[0]

        self.__main_group.add_argument("-" + short_opt, "--" + long_opt, help=desc, dest=long_opt, action=action, default=default, required=required, *args, **kwargs)

    def accept_positional_arguments(self, name, desc, *args, **kwargs):
        """
            Use this method if positonal arguments are going to be used
        """
        self.__parser.add_argument(name, help=desc, nargs='*', action="store", *args, **kwargs)

    def parse(self, args=None):
        return self.__parser.parse_args(args=args)


class Template:
    _VERSION_NUMBER = "1.0"
    _MODULE_FILE = sys.executable if getattr(sys, 'frozen', False) else __file__
    _PROGRAM_NAME = os.path.basename(_MODULE_FILE)
    _PROGRAM_DIR = os.path.abspath(os.path.dirname(_MODULE_FILE))
    _COMMAND_LIST_STR_DESC = [["list", "list values"],
                              ["comp", "compare values"]]
    _COMMAND_LIST_STR = {c for c, _ in _COMMAND_LIST_STR_DESC}

    _NOT_A_TTY = hasattr(sys.stdin, "fileno") and not os.isatty(sys.stdin.fileno())

    def __init__(self):
        self.__ARG_PARSER = ArgParser(self._PROGRAM_NAME, self._VERSION_NUMBER)
        self._logfile = ""
        self.__temp_directory = None
        self.__with_traceback = True
        self.__keep_temp_directory_flag = False
        self.__one_warning = False
        self.__args_defined = False
        self.__silent_mode = False

        # define arguments here: ex self.__output_file = None
        # so completion works

        try:
            # set binary mode on output/error stream for Windows
            import msvcrt
            msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
            msvcrt.setmode(sys.stderr.fileno(), os.O_BINARY)
        except:
            pass

    def _keep_temp_directory(self,keep=True):
        self.__keep_temp_directory_flag = keep

    def _create_temp_directory(self, temp_root=None):
        """
        defines self.__temp_directory
        """

        self.__temp_directory = os.path.join(temp_root or os.getenv("TEMP"), "{}_{}_{}".format(os.path.splitext(self._PROGRAM_NAME)[0], os.getpid(), threading.current_thread().name))
        if not os.path.isdir(self.__temp_directory):
            os.mkdir(self.__temp_directory)
        return self.__temp_directory

    @staticmethod
    def _glob(filelist):
        """
        converts a list of files to a list of files with
        expanded wildcards
        """
        return [f for filename in filelist for f in glob.glob(filename)]

    def _delete_temp_directory(self):
        if self.__temp_directory:
            if self.__keep_temp_directory_flag:
                self._warn("Keeping temp dir {}".format(self.__temp_directory))
            else:
                rc,output = python_lacks.rmtree(self.__temp_directory)
                if rc == 0:
                    self.__temp_directory = None
                else:
                    self._warn("Could not delete temp dir '{}': {}".format(self.__temp_directory,output))

    def init_from_custom_args(self, args):
        """
        module mode, with arguments like when called in standalone
        """
        self.__parse_args(args)
        self.__purge_log()
        rc = self._doit()
        # cleanup argument attributes
        # Parse passed args

        for key, value in self.__options.__dict__.items():
            delattr(self, "_%s" % self.__get_variable_name(key))

        # perform cleanup just when like ran from command line

        self._child_cleanup()
        self._delete_temp_directory()

        return rc

    def _child_cleanup(self):
        """
        override this method and add what needed, like resource free, drive dismount...
        """
        pass

    def _init_from_sys_args(self):
        """ standalone mode """
        rc = 0

        try:
            rc = self.__do_init()
        except Exception as e:
            # catch exception
            if self.__with_traceback and not isinstance(e,argparse.UnrecognizedArgumentsError):
                # get full exception traceback
                print('{}{}{}'.format(colorama.Fore.LIGHTRED_EX,traceback.format_exc(),colorama.Fore.RESET))
            else:
                self._message('{}{}{}'.format(colorama.Fore.LIGHTRED_EX,
                python_lacks.ascii_compliant(str(e), best_ascii_approximation=True),
                colorama.Fore.RESET))


            sys.exit(1)
        finally:
            self._child_cleanup()
            self._delete_temp_directory()

        return rc or 0

    # uncomment if module mode is required
    ##    def init(self,output_file):
    ##        """ module mode """
    ##        # set the object parameters using passed arguments
    ##        self.__output_file = output_file
    ##        self.__purge_log()
    ##        self.__doit()

    def __do_init(self):
        # count_usage.count_usage(self._PROGRAM_NAME,1)
        self.__keep_temp_directory_flag = False
        self.__parse_args()
        self.__purge_log()
        return self._doit()

    def __purge_log(self):
        if self._logfile:
            try:
                os.remove(self._logfile)
            except OSError:
                pass

    def _set_silent_mode(self, mode=True):
        self.__silent_mode = mode

    def _message(self, msg, with_prefix=True):
        if not self.__silent_mode:
            if with_prefix:
                msg = "{}: {}\n".format(self._PROGRAM_NAME, msg)
            else:
                msg += "\n"

            sys.stderr.write(msg)
            sys.stderr.flush()

            if self._logfile:
                f = open(self._logfile, "a")
                f.write(msg)
                f.close()

    def _error(self, msg, user_error=True, with_traceback=False):
        """
        set user_error to False to trigger error report by e-mail
        """
        self.__silent_mode = False
        self.__with_traceback = with_traceback
        raise Exception("*** Error: " + msg + " ***")

    def _warning_raised(self):
        return self.__one_warning

    def _warn(self, msg):
        self._message('{}Warning: {} {}'.format(colorama.Fore.YELLOW,msg,colorama.Fore.RESET))
        self.__one_warning = True

    @staticmethod
    def __get_variable_name(v):
        return "".join([x.lower() if x.isalnum() else "_" for x in v])

    def __parse_args(self, args=None):
        # Define authorized args
        if not self.__args_defined:
            self._define_args(self.__ARG_PARSER)
            self.__args_defined = True

        # Parse passed args
        self.__options = self.__ARG_PARSER.parse(args=args)
        for key, value in self.__options.__dict__.items():
            setattr(self, "_%s" % self.__get_variable_name(key), value)

    def _define_args(self, parser):
        # Note :
        # Each long opt will correspond to a variable which can be exploited in the "doit" phase
        # All '-' will be converted to '_' and every upper chars will be lowered
        # Standard argparse parameters can also be used (eg. type=int for automatic convertion)
        # Exemple :
        #   My-Super-Opt --> self.__my_super_opt
        parser.accept_positional_arguments("filenames", "Files to process")
        parser.add_argument("command=", "specify command (among %s)" % ",".join(self._COMMAND_LIST_STR), required=True)
        parser.add_argument("output-file=", "specify output file", required=True)
        parser.add_argument("More_Complex_one=[]", "This is an argument that you can pass more than once", short_opt="MC")
        parser.add_argument("use-print", "Flag argument (True/False)")
        parser.add_argument("max-lines=", "Maximum number of lines", type=int)

    def _doit(self):
        if self._command not in self._COMMAND_LIST_STR:
            self._error("Command %s not recognized. Valid commands are: %s" % (self._command, ",".join(self._COMMAND_LIST_STR)))
        # main processing here
        print(self._command)
        # main processing here
        print("filenames/extra args=", self._filenames)
        print("output_file", self._output_file)
        print("list", self._more_complex_one)
        print("boolean", self._use_print)
        return 0


if __name__ == '__main__':
    """
        Description :
            Main application body
    """

    o = Template()
    rc = o._init_from_sys_args()
    sys.exit(rc)
    # o.init("output_file")
