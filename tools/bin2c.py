import os,glob
import sys
from functools import reduce

import cli_template

if str is not bytes:
    # python 3:
    ord = int


class Tool(cli_template.Template):
    _VERSION_NUMBER = "1.0"
    _MODULE_FILE = sys.executable if getattr(sys, 'frozen', False) else __file__
    _PROGRAM_NAME = os.path.basename(_MODULE_FILE)
    _PROGRAM_DIR = os.path.abspath(os.path.dirname(_MODULE_FILE))


    def __create_c(self, input_file):
        with open(input_file, "rb") as f:
            contents = f.read()
        if self._alignment is None:
            alignment = 16
        else:
            alignment = int(self._alignment)

        outbase = os.path.basename(os.path.splitext(input_file)[0])
        output_file = os.path.join(self._output_directory, outbase + ".c")
        if not os.path.isdir(self._output_directory):
            os.makedirs(self._output_directory)

        if input_file != output_file:
            offset = 0
            with open(output_file, "w") as fw:
                fw.write('#include "{0}.h"\n\nconst unsigned char {0}[0x{1:x}] = {{\n'.format(outbase, len(contents)))
                length = 3
                while offset < len(contents):
                    fw.write("{}{}{}     // 0x{:06X}".format(" " * length,
                                                                ",".join("0x{:02X}".format(ord(item)) for item in contents[offset:offset + alignment]),
                                                                "," if offset + alignment < len(contents) else " ",
                                                                offset))
                    offset += alignment
                    if offset < len(contents):
                        fw.write("\n")
                fw.write("\n};")

        with open(output_file.replace(".c", ".h"), "w") as f:
            f.write("#ifndef {0}\n#define {0}\n\n".format(outbase.upper() + "_H"))
            f.write("extern const unsigned char {}[0x{:x}];\n\n#endif\n".format(outbase, len(contents)))

    def _doit(self):
        for input_file in self._filenames:
            g = glob.glob(input_file)
            # make sure that all wildcard passed match something
            if not g:
                self._error("{}: no match".format(input_file))
            for i in g:
                self.__create_c(i)

    def _define_args(self, parser):
        # Note :
        # Each long opt will correspond to a variable which can be exploited in the "doit" phase
        # All '-' will be converted to '_' and every upper chars will be lowered
        # Standard argparse parameters can also be used (eg. type=int for automatic convertion)
        # Exemple :
        #   My-Super-Opt --> self.__my_super_opt
        # parser.accept_positional_arguments("filenames", "Files to process")
        parser.accept_positional_arguments("filenames", "Files to proceed")
        parser.add_argument("output-directory=", "specify output directory", required=True)
        parser.add_argument("alignment=", "specify width alignment (in bytes)")


if __name__ == '__main__':
    """
        Description :
            Main application body
    """

    o = Tool()
    rc = o._init_from_sys_args()
    sys.exit(rc)
    # o.init("output_file")
