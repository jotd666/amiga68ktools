import whdslave_wrapper,sys,os,subprocess


print("*** wrapping...")

input_slave = os.path.abspath(sys.argv[1])
w = whdslave_wrapper.WHDSlaveWrapper()
w.init_from_custom_args(["-i",input_slave])

output_slave_prefix = os.path.splitext(input_slave)[0]+"_wrapped"

mkf = os.path.join(os.path.dirname(input_slave),"makefile_windows.mak")
if not os.path.exists(mkf):
    with open(mkf,"w") as f:
        # if doesn't exist, hardcode
        f.write(r"""PROGNAME = {}\nWHDLOADER = $(PROGNAME).slave
SOURCE = $(PROGNAME)HD.s
WHDBASE = K:\jff\AmigaHD\PROJETS\WHDLoad
all :  $(WHDLOADER)

$(WHDLOADER) : $(SOURCE)
	wdate.py> datetime
	vasmm68k_mot -DDATETIME -IK:/jff/AmigaHD/amiga39_JFF_OS/include -I$(WHDBASE)\Include -phxass -nosym -Fhunkexe -o $(WHDLOADER) $(SOURCE)
""".format(output_slave_prefix))
print("*** assembling...")
os.putenv("PROGNAME",output_slave_prefix)
output = subprocess.check_output([r"C:\SysGCC\arm-eabi\bin\make","-e","-f","makefile_windows.mak"],cwd=os.path.dirname(input_slave))
print(output.decode())
input("*** Done. Press RETURN ...")