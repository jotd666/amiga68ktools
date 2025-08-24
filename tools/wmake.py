import subprocess,sys,re
import argparse


parser = argparse.ArgumentParser()
parser.add_argument("makefile_params", nargs='*')
parser.add_argument("-n","--noretry", help="no retry",action="store_true")
parser.add_argument("-N","--nodelay", help="no delay on end",action="store_true")
parser.add_argument("-u","--print-undefined-references", help="display undefined references summary",action="store_true")
parser.add_argument("-m","--makefile", help="makefile name",default="makefile")
args = parser.parse_args()

undefined_re = re.compile("undefined reference to `(.*)'")

print("building from {}...".format(args.makefile))
rc = 0
undef = set()
while True:

    p = subprocess.Popen([r"make","-f",args.makefile]+args.makefile_params,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    for line in p.stdout:
        line = line.decode(errors="ignore")
        if args.print_undefined_references:
            m = undefined_re.search(line)
            if m:
                s = m.group(1)
                undef.add(s)
        else:
            print(line.rstrip())

    rc = p.wait()
    if undef:
        print("{} undefined:".format(len(undef)))
        for u in sorted(undef):
            print(u)

    if rc and not args.noretry:
        input("*** Press return to retry ***")
    else:
        break
    undef.clear()

if not args.nodelay:
    import time
    time.sleep(4)

sys.exit(rc)
