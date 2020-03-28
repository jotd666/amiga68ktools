import difflib,subprocess,sys,re,os

if len(sys.argv)<3:
    print("Usage: {} file1 file2".format(os.path.basename(__file__)))
    sys.exit()

file1 = sys.argv[1]
file2 = sys.argv[2]

r = re.compile("LAB_....")

def readlines(filepath):
    if os.path.splitext(filepath)[1].lower() in [".asm",".s"]:
        pass
    else:
        subprocess.check_call(["ira","-a",filepath])
        filepath = os.path.splitext(filepath)[0]+".asm"
    with open(filepath) as f:
        lines = list(f)
        return [x.rstrip() for x in lines],[r.sub("LAB_XXXX",l).partition(";")[0] for l in lines]

lines1,filtered_lines1 = readlines(file1)
lines2,filtered_lines2 = readlines(file2)

for line in difflib.unified_diff(filtered_lines1, filtered_lines2, fromfile=file1, tofile=file2, lineterm=''):
    m = re.match(r"@@..(\d+),(\d+)\D+(\d+),(\d+)",line)
    if m:
        start,end,start2,end2 = [int(x) for x in m.groups()]
        print(line)
        for i in range(start,start+end):
            j = min(max(i-start2+start,0),len(lines2)-1)
            i = min(i,len(lines1)-1)
            l1,l2 = lines1[i],lines2[j]
            if l1.startswith("\t") and l2.startswith("\t"):
                # asm instruction probably
                fw1 = l1.split()[0]
                fw2 = l2.split()[0]
                if fw1 != fw2:
                    l1 = "**"+l1
                    l2 = "**"+l2
            print("{} <=> {}".format(l1,l2))


