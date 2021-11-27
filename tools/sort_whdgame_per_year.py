import sys,os,shutil
import argparse,whdload_slave

parser = argparse.ArgumentParser()
parser.add_argument("root1", help="root of games to scan")
parser.add_argument("root2", help="output root")
parser.add_argument("-c","--copy", help="copy instead of move",
                    action="store_true")
parser.add_argument("-t","--test", help="test mode, just print info",
                    action="store_true")
args = parser.parse_args()

input_root = args.root1
output_root = args.root2
copy_opt = args.copy
test_mode = args.test


if not os.path.isdir(output_root):
    os.mkdir(output_root)

d = dict()

# pass 1: collect years in slaves
# if there are several slaves in the same dir, the last slave found
# overwrites the first(s)

nb_old_slaves = 0

for root,_,files in os.walk(input_root):
    for f in files:
        if f.lower().endswith(".slave"):
            slave_file = os.path.join(root,f)
            slave = whdload_slave.WHDLoadSlave(slave_file)
            if slave.error:
                continue
            if slave.slave_copyright:
                year = slave.slave_copyright.split()[0].split("/")[0]
                try:
                    year = int(year)
                    # fix small issues
                    if year < 100:
                        year += 1900
                    elif year < 1900:
                        year  = 1900 + (year%100)
                except ValueError:
                    nb_old_slaves += 1
                    print("{}: slave has unparsable date {}, copy/move manually".format(slave_file,year))
                    year = 0
            else:
                print("{}: slave is too old, no copyright, copy/move manually".format(slave_file))
                year = 0
                nb_old_slaves += 1

            d[root] = year

if test_mode:
    years = set(d.values())
    if 0 in years:
        years.remove(0)
    max_year = max(years)
    min_year = min(years)

    print("{} games found, {} years ranging from {} to {}".format(len(d),len(years),min_year,max_year))
    print("{} too old slaves".format(nb_old_slaves))
    sys.exit(0)

func = shutil.copytree if copy_opt else shutil.move

# create year dirs once only
for year in years:
    yd = os.path.join(output_root,year)
    if not os.path.exists(yd):
        os.mkdir(yd)

for game,year in d.items():
    dest = os.path.join(output_root,os.path.join(year,os.path.basename(game)))
    if not os.path.isdir(dest):
        #print("processing {} ({})".format(game,year))
        func(game,dest)