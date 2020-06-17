import sys,subprocess,os,shutil
import ira_asm_tools,re

if __name__ == '__main__':
    tempdir = os.getenv("TEMP")
    input_filename = os.path.basename(sys.argv[1])
    input_file=os.path.join(tempdir,input_filename)
    shutil.copy(sys.argv[1],input_file)
    subprocess.check_call(["ira","-a",input_filename],cwd=tempdir,stdout=subprocess.DEVNULL)
    output_file = os.path.join(tempdir,os.path.basename(os.path.splitext(input_file)[0])+".asm")
    # completely broken now...
    af = ira_asm_tools.AsmFile(output_file,input_filename)
    for line in af.lines:
        if re.search("LAB_....\+?\d?,",line):
            print(line)
        if re.search("PEA\s+LAB_....[^(]",line):
            print(line)
        elif re.search("DC\.L.*LAB_....",line): # happens like PL_L $xxx,load instead of PL_P
            print(line)