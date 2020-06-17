import difflib,subprocess,sys,re,os
import argparse
parser = argparse.ArgumentParser()
parser.add_argument("file1", help="file 1")
parser.add_argument("file2", help="file 2")
parser.add_argument("-i","--ignore-a4", help="ignore A4-relative offsets",
                    action="store_true")
parser.add_argument("-w","--work-dir",help="store temp asm files into work dir")
args = parser.parse_args()

file1 = args.file1
file2 = args.file2

r = re.compile("(LAB_|EXT_)....(\+\d)?")

def readlines(filepath):
    if os.path.splitext(filepath)[1].lower() in [".asm",".s"]:
        pass
    else:
        subprocess.check_call(["ira","-a",filepath])
        filepath = os.path.splitext(filepath)[0]+".asm"
    with open(filepath) as f:
        lines = [x.rstrip() for x in f]
        rval = [lines,[r.sub(r"\1XXXX",l).partition(";")[0] for l in lines]]
        if args.ignore_a4:
            rval[1] = [re.sub("\(-?\d+,A4\)","(-XX,A4)",re.sub("\d+\(A4\)","XX(A4)",x)) for x in rval[1]]
        rval[1] = [x for x in rval[1] if not x.startswith("LAB_XXXX:")]
        return rval

lines1,filtered_lines1 = readlines(file1)
lines2,filtered_lines2 = readlines(file2)

if args.work_dir:
    with open(os.path.join(args.work_dir,file1+"_xxx.asm"),'w') as f:
        f.writelines("{}\n".format(x) for x in filtered_lines1)
    with open(os.path.join(args.work_dir,file2+"_xxx.asm"),'w') as f:
        f.writelines("{}\n".format(x) for x in filtered_lines2)

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


