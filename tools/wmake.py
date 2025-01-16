import subprocess,sys
import argparse


parser = argparse.ArgumentParser()
parser.add_argument("makefile_params", nargs='*')
parser.add_argument("-n","--noretry", help="no retry",action="store_true")
parser.add_argument("-m","--makefile", help="makefile name",default="makefile")
args = parser.parse_args()

print("building from {}...".format(args.makefile))
rc = 0
while True:
    try:
        subprocess.check_call([r"make","-f",args.makefile]+args.makefile_params)
    except Exception:
        rc = 1
        if args.noretry:
            break
        input("*** Press return to retry ***")
    break
import time
time.sleep(4)

sys.exit(rc)
