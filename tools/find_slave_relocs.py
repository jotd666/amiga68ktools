import sys,subprocess,os,shutil
import ira_asm_tools,re

if __name__ == '__main__':
    tempdir = os.getenv("TEMP")
    input_filename = os.path.basename(sys.argv[1])
    input_file=os.path.join(tempdir,input_filename)
    shutil.copy(sys.argv[1],input_file)
    subprocess.check_call(["ira","-a",input_filename],cwd=tempdir,stdout=subprocess.DEVNULL,stderr=subprocess.STDOUT)
    output_file = os.path.join(tempdir,os.path.basename(os.path.splitext(input_file)[0])+".asm")

    found = False
    def hit(line):
        global found
        print(line)
        found = True
    af = ira_asm_tools.AsmFile(output_file,input_filename)
    for line in af.lines:
        line = line.rstrip()
        if re.search("LAB_....,",line):
            hit(line)
        elif re.search(r"LAB_....\+\d,",line):
            hit(line)
        elif re.search("PEA\s+LAB_....[^(]",line):
            hit(line)
        elif re.search("DC\.L.*LAB_....",line): # happens like PL_L $xxx,load instead of PL_P
            hit(line)

    if not found:
        print("No relocs found")