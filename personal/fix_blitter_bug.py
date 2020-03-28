import os

def get_address(t):
    return int(t[1:],16)

entry = dict()
REGISTER = 0
DIRECT = 1
IMMEDIATE = 2

with open(r"C:\DATA\jff\AmigaHD\Download\.whdl_register") as f:
    previous_line = None
    toklist =[]
    for line in f:
        if len(line)>4 and line[1:4] == "1m$":
            print(line)
            toklist.append(previous_line.split())
            next(f)
            next(f)
            next(f)
        previous_line = line
    for toks in toklist:
        address = get_address(toks[0])
        instruction = toks[1]
        args = [x.strip("()") for x in toks[2].split(",")]
        if len(args)==2:
            custom_address = get_address(args[1])
            if 0xDFF000 < custom_address < 0xDFF100:
                firstchar = args[0][0]
                if firstchar=="$":
                    source = get_address(args[0])
                    entry[address] = (instruction,source,custom_address,DIRECT)
                elif firstchar=="#":
                    source = get_address(args[0][1:])
                    entry[address] = (instruction,source,custom_address,IMMEDIATE)

                else:
                    entry[address] = (instruction,args[0],custom_address,REGISTER)

                print("{:x} {}".format(address,entry[address]))

patchlist=[]
patchfuncs=[]
bf = set()

for address,(instruction,source,custom_address,at) in sorted(entry.items()):
    if at == IMMEDIATE:
        blitwait_func = "blitwait_imm_{:x}_{:03x}".format(source,custom_address % 0x1000)
        l = "\tPL_PSS\t${:x},{},4\n".format(address,blitwait_func)
        p = "{}:\n\tbsr\twait_blit\n\t{}\t#${:x},${:x}\n\trts\n".format(blitwait_func,instruction,source,custom_address)

    elif at == DIRECT:
        blitwait_func = "blitwait_{:x}_{:03x}".format(source,custom_address % 0x1000)
        l = "\tPL_PSS\t${:x},{},4\n".format(address,blitwait_func)
        p = "{}:\n\tbsr\twait_blit\n\t{}\t${:x},${:x}\n\trts\n".format(blitwait_func,instruction,source,custom_address)

    elif at == REGISTER:
        blitwait_func = "blitwait_r{}_{:03x}".format(source,custom_address % 0x1000)
        l = "\tPL_PS\t${:x},{}\n".format(address,blitwait_func)
        p = "{}:\n\tbsr\twait_blit\n\t{}\t{},${:x}\n\trts\n\n".format(blitwait_func,instruction,source,custom_address)
    patchlist.append(l)
    if blitwait_func not in bf:
        patchfuncs.append(p)
    bf.add(blitwait_func)

outdir = r"C:\DATA\jff\AmigaHD\PROJETS\HDInstall\ARetoucher\BallRaiderIIHDDev"
output = os.path.join(outdir,"fixblits.s")

with open(output,"w") as f:
    f.write("pl_blits:\n\tPL_START\n")
    f.writelines(patchlist)
    f.write("\tPL_END\n\n")
    f.writelines(patchfuncs)
import subprocess
subprocess.check_call("echo YES| build.bat >NUL",shell=True,cwd=outdir)
